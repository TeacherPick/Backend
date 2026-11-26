import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import Settings, get_settings, password_hasher
from app.db import make_engine
from app.main import create_app
from app.models import Account

PASSWORD = "local test password"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def mysql_settings() -> Settings:
    if os.environ.get("RUN_MYSQL_TESTS") != "1":
        pytest.skip("Set RUN_MYSQL_TESTS=1 and configure a dedicated MySQL *_test schema.")
    settings = get_settings()
    if not settings.db_name.endswith("_test"):
        pytest.fail("The integration database name must end with _test.")
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    return settings.model_copy(update={
        "reset_code_pepper": Settings(reset_code_pepper="g" * 32).reset_code_pepper,
        "smtp_host": "localhost",
        "smtp_sender": "platform@example.com",
    })


@pytest.fixture
def client(mysql_settings: Settings):
    with TestClient(create_app(mysql_settings)) as test_client:
        yield test_client


@pytest.fixture
def db(mysql_settings: Settings):
    engine = make_engine(mysql_settings)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def user(client: TestClient):
    def create(role: str = "teacher", name: str = "테스트 사용자"):
        username = f"test_{uuid.uuid4().hex}"
        email = f"{username}@example.com"
        registered = client.post("/api/v1/auth/register", json={
            "username": username, "name": name, "email": email, "role": role,
            "password": PASSWORD, "password_confirmation": PASSWORD,
        })
        assert registered.status_code == 201, registered.text
        login = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return registered.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}
    return create


@pytest.fixture
def administrator(client: TestClient, db: Session):
    username = f"admin_{uuid.uuid4().hex}"
    account = Account(
        username=username, email=f"{username}@example.com", name="테스트 관리자",
        role="admin", password_hash=password_hasher.hash(PASSWORD),
    )
    db.add(account)
    db.commit()
    login = client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return username, {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
def post(client: TestClient, user):
    instructor, headers = user("instructor", "김 강사")
    created = client.post("/api/v1/posts", headers=headers, json={
        "title": f"교육 {uuid.uuid4().hex}", "body": "학생을 위한 실습 프로그램",
        "category": "프로그래밍", "audience": "중학교", "scale": "학급", "region": "서울",
        "duration_minutes": 90,
    })
    assert created.status_code == 201, created.text
    return created.json(), instructor, headers
