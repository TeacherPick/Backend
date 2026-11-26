from uuid import uuid4

from fastapi.testclient import TestClient

from app.core import Settings
from app.main import create_app
from app.models import Account
from tests.conftest import PASSWORD

PREFIX = "/api/v1"


def test_database_health(client):
    assert client.get(f"{PREFIX}/health").json() == {"status": "ok", "database": "reachable"}


def test_separate_frontend_origin():
    origin = "http://127.0.0.1:5173"
    headers = {"Origin": origin, "Access-Control-Request-Method": "PATCH",
               "Access-Control-Request-Headers": "authorization,content-type"}
    with TestClient(create_app(Settings(cors_origins=[origin]))) as standalone:
        assert standalone.get("/static/controller.js").status_code == 404
        response = standalone.options(f"{PREFIX}/auth/me", headers=headers)
        assert response.status_code == 200 and response.headers["access-control-allow-origin"] == origin
        rejected = standalone.options(f"{PREFIX}/auth/me", headers={**headers, "Origin": "https://other.example"})
        assert rejected.status_code == 400 and "access-control-allow-origin" not in rejected.headers


def test_profile_registration_account_edit_and_privacy(client, db, administrator):
    username = f"org_{uuid4().hex}"
    email = f"{username}@example.com"
    registration = {
        "username": username, "name": "서버 연동 강사", "email": email, "role": "instructor",
        "password": PASSWORD, "password_confirmation": PASSWORD, "organization": "테스트 기관",
        "phone": "010-1234-5678", "profile": {"kind": "company", "specialty": f"파이썬 {username}", "distance_km": 10},
    }
    assert client.post(f"{PREFIX}/auth/register", json={**registration, "role": "teacher"}).status_code == 422
    result = client.post(f"{PREFIX}/auth/register", json=registration)
    assert result.status_code == 201, result.text
    account_id = result.json()["id"]
    response = client.get(f"{PREFIX}/instructors", params={"q": username, "kind": "company", "max_distance": 10})
    public = next(row for row in response.json()["items"] if row["id"] == account_id)
    assert public["organization"] == registration["organization"]
    assert "phone" not in public and "email" not in public

    login = client.post(f"{PREFIX}/auth/login", json={"username": username, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"{PREFIX}/auth/me", headers=headers).json()["phone"] == registration["phone"]
    new_email = f"new_{email}"
    data = {"name": "새 이름", "email": new_email, "organization": None, "phone": None}
    assert client.patch(f"{PREFIX}/auth/me", headers=headers, json=data).status_code == 403
    saved = client.patch(f"{PREFIX}/auth/me", headers=headers, json={**data, "current_password": PASSWORD})
    assert saved.status_code == 200 and saved.json()["email"] == new_email
    _, admin_headers = administrator
    search = client.get(f"{PREFIX}/admin/accounts", headers=admin_headers, params={"q": new_email})
    assert [row["id"] for row in search.json()["items"]] == [account_id]
    assert client.delete(f"{PREFIX}/admin/accounts/{account_id}", headers=admin_headers).status_code == 204
    member = db.get(Account, account_id)
    assert member.phone is None and member.organization is None and member.email is None
    assert client.get(f"{PREFIX}/auth/me", headers=headers).status_code == 401


def test_catalog_filters_owned_items_and_comment_edit(client, user, post):
    program, _, owner_headers = post
    _, teacher_headers = user()
    _, stranger_headers = user()
    post_id = program["id"]
    path = f"{PREFIX}/posts/{post_id}"
    updated = client.patch(path, headers=owner_headers, json={"price": 0, "distance_km": 9})
    assert updated.status_code == 200 and updated.json()["price"] == 0
    filters = {"q": program["title"], "max_price": 0, "max_distance": 9, "sort": "comments"}
    assert client.get(f"{PREFIX}/posts", params=filters).json()["total"] == 1
    assert client.get(f"{PREFIX}/posts", params={**filters, "max_distance": 8}).json()["total"] == 0
    assert client.get(f"{PREFIX}/me/posts", headers=owner_headers).json()["total"] == 1
    assert client.get(f"{PREFIX}/me/posts", headers=teacher_headers).json()["total"] == 0

    comment = client.post(f"{path}/comments", headers=teacher_headers, json={"body": "초안"}).json()
    url = f"{path}/comments/{comment['id']}"
    assert client.patch(url, headers=stranger_headers, json={"body": "변경"}).status_code == 403
    assert client.patch(url, headers=teacher_headers, json={"body": ""}).status_code == 422
    assert client.patch(url, headers=teacher_headers, json={"body": "수정"}).json()["body"] == "수정"
    assert client.get(f"{path}/comments").json()["total"] == 1
    assert client.post(f"{path}/reviews", headers=teacher_headers, json={"body": "후기", "rating": 4}).status_code == 201
    own = client.get(f"{PREFIX}/me/reviews", headers=teacher_headers).json()
    assert own["items"][0]["post_title"] == program["title"] and own["average_rating"] == 4
    summary = client.get(f"{PREFIX}/posts", params={**filters, "sort": "rating"}).json()["items"][0]
    assert (summary["average_rating"], summary["comment_count"]) == (4, 1)
