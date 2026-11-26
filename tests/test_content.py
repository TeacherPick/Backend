import json
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core import now_utc
from app.manage import set_profile
from app.models import Comment, Post, PostAttachment, Reaction, Review
from app.services import content

PREFIX = "/api/v1"
PDF = b"%PDF-1.7\n"


def test_post_create_edit_search_attachments_and_delete(client, post, user, db):
    record, instructor, owner = post
    _, teacher = user()
    out = {key: record[key] for key in ("title", "body", "category", "audience", "scale")}
    listing = PREFIX + "/posts"
    assert client.post(listing, headers=teacher, json=out).status_code == 403
    assert client.post(listing, json=out).status_code == 401
    assert client.post(listing, headers=owner, json={**out, "title": "  "}).status_code == 422
    invalid = client.post(
        listing, headers=owner, data={"data": json.dumps(out)},
        files={"files": ("unsafe.pdf", b"invalid", "application/pdf")},
    )
    assert invalid.status_code == 415
    added = client.post(
        listing, headers=owner, data={"data": json.dumps(out)},
        files={"files": ("sample.pdf", PDF, "application/pdf")},
    )
    assert added.status_code == 201, added.text
    created = added.json()
    path = f"{listing}/{created['id']}"
    file_id = created["attachments"][0]["id"]
    download = client.get(f"{path}/attachments/{file_id}")
    assert download.content == PDF
    assert "attachment;" in download.headers["content-disposition"]
    assert client.patch(path, headers=teacher, json={"title": "변경"}).status_code == 403
    assert client.patch(path, headers=owner, json={"title": None}).status_code == 422
    invalid_change = client.patch(
        path, headers=owner, data={"data": json.dumps({"title": "실패", "remove_attachment_ids": [file_id]})},
        files={"files": ("sample.pdf", b"invalid", "application/pdf")},
    )
    assert invalid_change.status_code == 415
    assert client.get(f"{path}/attachments/{file_id}").content == PDF
    changed_title = record["title"] + " 수정"
    edited = client.patch(
        path, headers=owner, data={"data": json.dumps({"title": changed_title, "remove_attachment_ids": [file_id]})},
        files={"files": ("replacement.pdf", PDF, "application/pdf")},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == changed_title
    assert edited.json()["updated_at"] > created["updated_at"]
    assert edited.json()["attachments"][0]["id"] != file_id
    assert client.get(f"{path}/attachments/{file_id}").status_code == 404
    assert client.get(path).json()["view_count"] == 1
    assert client.get(path).json()["view_count"] == 2
    assert client.get(listing, params={"q": changed_title, "sort": "views", "size": 1}).json()["items"][0]["id"] == created["id"]
    assert client.get(listing, params={"q": record["title"], "region": "서울"}).json()["total"] == 1
    assert client.get(listing, params={"q": instructor["name"], "category": "프로그래밍"}).json()["total"] >= 1
    assert client.delete(path, headers=teacher).status_code == 403
    assert client.delete(path, headers=owner).status_code == 204
    assert client.get(path).status_code == 410
    assert db.get(Post, created["id"]) is None
    assert db.scalar(select(func.count()).select_from(PostAttachment).where(PostAttachment.post_id == created["id"])) == 0


def test_replies_and_parent_tombstones(client, post, user):
    record, _, owner = post
    _, teacher = user()
    url = f"{PREFIX}/posts/{record['id']}/comments"
    assert client.post(url, json={"body": "댓글"}).status_code == 401
    assert client.post(url, headers=teacher, json={"body": " "}).status_code == 422
    root = client.post(url, headers=teacher, json={"body": "첫 댓글"}).json()
    reply = client.post(url, headers=owner, json={"parent_id": root["id"], "body": "답변"}).json()
    assert client.post(url, headers=teacher, json={"parent_id": reply["id"], "body": "하위 답변"}).status_code == 422
    root_path = f"{url}/{root['id']}"
    assert client.delete(root_path, headers=owner).status_code == 403
    assert client.delete(root_path, headers=teacher).status_code == 204
    result = client.get(url).json()
    assert result["total"] == 1
    assert result["items"][0]["body"] == "삭제된 댓글입니다."
    assert result["items"][0]["author"] is None
    assert result["items"][0]["replies"][0]["id"] == reply["id"]
    assert client.post(url, headers=owner, json={"parent_id": root["id"], "body": "다른 답변"}).status_code == 410
    assert client.delete(f"{url}/{reply['id']}", headers=owner).status_code == 204
    assert client.get(url).json() == {"items": [], "total": 0}
    assert client.delete(f"{PREFIX}/posts/{record['id']}", headers=owner).status_code == 204


def test_reaction_toggle_switch_and_cooldown(client, post, user, monkeypatch):
    record, _, owner = post
    _, voter = user()
    url = f"{PREFIX}/posts/{record['id']}/reaction"
    assert client.post(url, headers=owner, json={"value": 1}).status_code == 403
    assert client.post(url, json={"value": 1}).status_code == 401
    assert client.post(url, headers=voter, json={"value": 0}).status_code == 422
    assert client.post(url, headers=voter, json={"value": 1}).json() == {"likes": 1, "dislikes": 0, "current": 1}
    assert client.post(url, headers=voter, json={"value": 1}).status_code == 429
    mock_clock = [now_utc() + timedelta(seconds=2)]
    monkeypatch.setattr(content, "now_utc", lambda: mock_clock[0])
    assert client.post(url, headers=voter, json={"value": -1}).json() == {"likes": 0, "dislikes": 1, "current": -1}
    assert client.get(url).json() == {"likes": 0, "dislikes": 1, "current": None}
    mock_clock[0] += timedelta(seconds=2)
    assert client.post(url, headers=voter, json={"value": -1}).json() == {"likes": 0, "dislikes": 0, "current": None}


def test_reviews_without_attendance_and_profile_metrics(client, post, user, db, tmp_path):
    record, instructor, owner = post
    first, teacher = user()
    _, another = user()
    path = f"{PREFIX}/posts/{record['id']}/reviews"
    assert client.post(path, json={"rating": 4, "body": "리뷰"}).status_code == 401
    assert client.post(path, headers=teacher, json={"rating": 6, "body": "리뷰"}).status_code == 422
    created = client.post(path, headers=teacher, json={"rating": 2, "body": "첫 리뷰"})
    assert created.status_code == 201
    assert client.post(path, headers=teacher, json={"rating": 4, "body": "중복"}).status_code == 409
    second = client.post(path, headers=another, json={"rating": 5, "body": "두 번째 리뷰"})
    assert second.status_code == 201
    result = client.get(path, params={"sort": "rating"}).json()
    assert result["average_rating"] == 3.5
    assert result["items"][0]["rating"] == 5
    edit_path = f"{path}/{created.json()['id']}"
    assert client.patch(edit_path, headers=owner, json={"rating": 4}).status_code == 403
    assert client.delete(edit_path, headers=owner).status_code == 403
    assert client.patch(edit_path, headers=teacher, json={"rating": 4}).json()["rating"] == 4
    profile_data = tmp_path / "profile.json"
    profile_data.write_text(json.dumps({"specialty": "파이썬", "bio": "강사 소개"}), encoding="utf-8")
    set_profile(db, Namespace(account_id=instructor["id"], source=profile_data))
    profile_url = f"{PREFIX}/instructors/{instructor['id']}"
    profile = client.get(profile_url).json()
    assert profile["programs"]["items"][0]["id"] == record["id"]
    assert profile["review_count"] == 2
    assert profile["average_rating"] == 4.5
    assert profile["specialty"] == "파이썬"
    assert client.get(profile_url + "/reviews").json()["total"] == 2
    assert client.get(f"{PREFIX}/instructors/{first['id']}").status_code == 404
    assert client.delete(edit_path, headers=teacher).status_code == 204
    assert client.get(path).json()["average_rating"] == 5


def test_concurrent_views_and_duplicate_review(client, post, user, db):
    record, _, _ = post
    _, headers = user()
    url = f"{PREFIX}/posts/{record['id']}"
    with ThreadPoolExecutor(max_workers=4) as workers:
        counts = list(workers.map(lambda _: client.get(url).json()["view_count"], range(8)))
        assert sorted(counts) == list(range(1, 9))
        statuses = list(workers.map(
            lambda _: client.post(url + "/reviews", headers=headers, json={"rating": 5, "body": "동시 리뷰"}).status_code,
            range(4),
        ))
    assert sorted(statuses) == [201, 409, 409, 409]
    assert db.get(Post, record["id"]).view_count == 8


def test_mysql_rejects_invalid_check_fk_and_unique(client, post, user, db):
    record, owner, headers = post
    _, teacher = user()
    root = client.post(f"{PREFIX}/posts/{record['id']}/comments", headers=teacher, json={"body": "부모 댓글"}).json()
    account_id = owner["id"]
    bad = [
        (Review(post_id=record["id"], author_id=account_id, rating=7, body="invalid"), 3819),
        (Reaction(post_id=record["id"], account_id=account_id, value=0), 3819),
        (Comment(post_id=record["id"], author_id=account_id, parent_id=9223372036854775800, body="invalid"), 1452),
    ]
    for row, error_number in bad:
        db.add(row)
        with pytest.raises(DBAPIError) as error:
            db.commit()
        assert error.value.orig.args[0] == error_number
        db.rollback()
    another = client.post(PREFIX + "/posts", headers=headers, json={
        "title": "또 다른 게시물", "body": "본문", "category": "IT", "audience": "고등학교", "scale": "학급",
    }).json()
    db.add(Comment(post_id=another["id"], author_id=account_id, parent_id=root["id"], body="invalid"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Reaction(post_id=record["id"], account_id=account_id, value=-1))
    db.commit()
    db.add(Reaction(post_id=record["id"], account_id=account_id, value=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
