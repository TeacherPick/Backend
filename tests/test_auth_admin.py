import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core import now_utc
from app.models import Account, AdminLoginAttempt, LoginSession, PasswordReset
from app.services import auth
from tests.conftest import PASSWORD

PREFIX = "/api/v1"


def test_signup_login_logout(client, user):
    account, headers = user()
    assert client.post(PREFIX + "/auth/register", json={
        **{key: account[key] for key in ("username", "name", "email", "role")},
        "password": PASSWORD, "password_confirmation": PASSWORD,
    }).status_code == 409
    assert client.post(PREFIX + "/auth/register", json={
        "username": "bad_role", "name": "관리자", "email": "bad_role@example.com", "role": "admin",
        "password": PASSWORD, "password_confirmation": PASSWORD,
    }).status_code == 422
    assert client.post(PREFIX + "/auth/login", json={
        "username": account["username"], "password": "wrong",
    }).json()["error"]["code"] == "invalid_password"
    assert client.post(PREFIX + "/auth/logout", headers=headers).status_code == 204
    assert client.get(PREFIX + "/dm/rooms", headers=headers).status_code == 401


def test_password_reset_with_expiry_and_single_use(client, user, db, monkeypatch):
    account, headers = user()
    email = account["email"]
    base = PREFIX + "/auth/password-reset"
    delivered = {}
    monkeypatch.setattr(auth, "send_reset_email", lambda _settings, address, code: delivered.update({address: code}))
    assert client.post(base + "/request", json={"email": email}).status_code == 202
    code = delivered[email]
    challenge = db.get(PasswordReset, account["id"])
    assert challenge.code_hash != code.encode()
    assert client.post(base + "/request", json={"email": f"absent_{uuid.uuid4().hex}@example.com"}).status_code == 202
    wrong = "999999" if code != "999999" else "000000"
    assert client.post(base + "/verify", json={"email": email, "code": wrong}).status_code == 400
    challenge.expires_at = now_utc() - timedelta(minutes=1)
    db.commit()
    assert client.post(base + "/verify", json={"email": email, "code": code}).status_code == 410
    challenge.created_at = now_utc() - timedelta(minutes=2)
    db.commit()
    assert client.post(base + "/request", json={"email": email}).status_code == 202
    verified = client.post(base + "/verify", json={"email": email, "code": delivered[email]})
    assert verified.status_code == 200
    new = "second test password"
    data = {"email": email, "ticket": verified.json()["ticket"], "password": new, "password_confirmation": new}
    assert client.post(base + "/confirm", json=data).status_code == 204
    assert client.post(base + "/confirm", json=data).status_code == 400
    assert client.get(PREFIX + "/dm/rooms", headers=headers).status_code == 401
    login = PREFIX + "/auth/login"
    assert client.post(login, json={"username": account["username"], "password": PASSWORD}).status_code == 401
    assert client.post(login, json={"username": account["username"], "password": new}).status_code == 200


def test_admin_login_limit_and_logout(client, db, administrator):
    username, original = administrator
    base = PREFIX + "/admin/auth"
    for _ in range(5):
        assert client.post(base + "/login", json={"username": username, "password": "wrong"}).status_code == 401
    limited = client.post(base + "/login", json={"username": username, "password": PASSWORD})
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    attempt = db.get(AdminLoginAttempt, username)
    attempt.blocked_until = now_utc() - timedelta(seconds=1)
    db.commit()
    assert client.post(base + "/login", json={"username": username, "password": PASSWORD}).status_code == 200
    assert client.post(PREFIX + "/auth/login", json={"username": username, "password": PASSWORD}).status_code == 401
    assert client.post(base + "/logout", headers=original).status_code == 204
    assert client.get(PREFIX + "/admin/accounts", headers=original).status_code == 401


def test_admin_accounts_posts_and_audit(client, db, administrator, post, user):
    record, instructor, owner = post
    _, admin_headers = administrator
    member, member_headers = user()
    path = f"{PREFIX}/posts/{record['id']}"
    remark = client.post(path + "/comments", headers=member_headers, json={"body": "후속 질문"})
    assert remark.status_code == 201
    admin_base = PREFIX + "/admin"
    assert client.get(admin_base + "/accounts", headers=owner).status_code == 403
    assert client.get(admin_base + "/accounts", headers=admin_headers).status_code == 200
    account_url = f"{admin_base}/accounts/{member['id']}"
    assert client.get(account_url, headers=admin_headers).json()["email"] == member["email"]
    assert client.get(account_url + "/comments", headers=admin_headers).json()["items"][0]["id"] == remark.json()["id"]
    assert client.get(f"{admin_base}/accounts/{instructor['id']}/posts", headers=admin_headers).json()["total"] == 1
    posts = client.get(admin_base + "/posts", headers=admin_headers, params={"q": record["title"]})
    assert posts.json()["items"][0]["id"] == record["id"]
    assert client.delete(account_url, headers=admin_headers).status_code == 204
    assert client.get(account_url, headers=admin_headers).status_code == 410
    assert client.get(PREFIX + "/dm/rooms", headers=member_headers).status_code == 401
    saved = db.get(Account, member["id"])
    assert all(getattr(saved, key) is None for key in ("username", "name", "email", "password_hash"))
    assert db.scalar(select(LoginSession.token_hash).where(LoginSession.account_id == member["id"])) is None
    assert client.delete(f"{admin_base}/posts/{record['id']}", headers=admin_headers).status_code == 204
    assert client.get(path).status_code == 410
    logged = client.get(admin_base + "/activity-logs", headers=admin_headers).json()["items"]
    assert any(
        item["resource"] == "comment" and item["resource_id"] == remark.json()["id"] and item["action"] == "create"
        for item in logged
    )
    assert any(
        item["resource"] == "post" and item["resource_id"] == record["id"] and item["action"] == "delete"
        for item in logged
    )
