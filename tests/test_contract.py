import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.dialects import mysql

from app.main import create_app
from app.models import Base

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "/api/v1"


def test_openapi_and_held_features():
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    operations = {"get", "post", "patch", "delete"}
    assert len(paths) == 36
    assert sum(len(operations & item.keys()) for item in paths.values()) == 48
    assert "security" in paths[PREFIX + "/admin/accounts"]["get"]
    assert "multipart/form-data" in paths[PREFIX + "/posts"]["post"]["requestBody"]["content"]
    assert "HTTPBearer" in response.json()["components"]["securitySchemes"]
    assert "/api/v1/dm/ws" in next(tag["description"] for tag in response.json()["tags"] if tag["name"] == "DM")
    code = json.dumps(paths, ensure_ascii=False).lower()
    assert not any(f"/{held}" in code for held in ("notices", "reports", "enrollments", "certifications", "blocks"))
    assert set(Base.metadata.tables).isdisjoint({"notices", "reports", "enrollments", "certifications", "blocks"})


def test_erd_includes_every_column_constraint_and_index():
    erd = (ROOT / "docs" / "erd.md").read_text(encoding="utf-8")
    for table in Base.metadata.tables.values():
        assert f"### {table.name}" in erd
        table_section = erd.split(f"### {table.name}\n", 1)[1].split("\n##", 1)[0]
        for column in table.columns:
            sql = column.type.compile(dialect=mysql.dialect())
            nullable = "예" if column.nullable else "아니오"
            assert f"| `{column.name}` | `{sql}` | {nullable} |" in table_section
        for index in table.indexes:
            assert index.name in table_section
        for constraint in table.constraints:
            if constraint.__class__.__name__ in {"CheckConstraint", "UniqueConstraint"}:
                assert constraint.name in table_section
        for fk in table.foreign_key_constraints:
            columns = ", ".join(fk.column_keys)
            target = ", ".join(element.column.name for element in fk.elements)
            assert f"({columns}) → {fk.referred_table.name}({target})" in table_section


def test_credential_validation_does_not_echo_values():
    with TestClient(create_app()) as client:
        response = client.post(PREFIX + "/auth/login", json={"username": "valid_id", "password": "x" * 150})
        assert response.status_code == 422
        assert "x" * 150 not in response.text
        assert response.json()["error"]["code"] == "validation_error"
        big = client.post(PREFIX + "/auth/login", content=b"0" * (256 * 1024 + 1))
        assert big.status_code == 413
        unknown_length = client.post(PREFIX + "/auth/login", content=iter([b"0" * (256 * 1024 + 1)]))
        assert unknown_length.status_code == 413
