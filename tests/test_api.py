"""Тесты REST API СМД: CRUD проектов, сравнение схем, миграции, healthcheck.

Требования ядра: Т1 (сравнение), Т2 (подсветка различий), Т3 (миграции).
"""
from fastapi.testclient import TestClient

SRC_DDL = """CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200)
);"""

TGT_DDL = """CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(200) NOT NULL
);
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL
);"""


def make_project(client: TestClient, name: str = "Демо-проект") -> dict:
    resp = client.post("/api/projects", json={"name": name, "description": "тест"})
    assert resp.status_code == 201
    return resp.json()


def make_comparison(client: TestClient, project_id: int, **kwargs) -> dict:
    payload = {
        "project_id": project_id,
        "name": "cmp-1",
        "dialect": "postgresql",
        "source_ddl": SRC_DDL,
        "target_ddl": TGT_DDL,
    }
    payload.update(kwargs)
    resp = client.post("/api/comparisons", json=payload)
    assert resp.status_code == 201
    return resp.json()


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "database": "ok"}


class TestProjects:
    def test_create_and_get(self, client: TestClient) -> None:
        project = make_project(client)
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Демо-проект"

    def test_list(self, client: TestClient) -> None:
        make_project(client, "проект-1")
        make_project(client, "проект-2")
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_duplicate_name_409(self, client: TestClient) -> None:
        make_project(client, "одинаковый")
        resp = client.post("/api/projects", json={"name": "одинаковый"})
        assert resp.status_code == 409

    def test_empty_name_422(self, client: TestClient) -> None:
        resp = client.post("/api/projects", json={"name": "   "})
        assert resp.status_code == 422

    def test_missing_field_422(self, client: TestClient) -> None:
        resp = client.post("/api/projects", json={"description": "без имени"})
        assert resp.status_code == 422

    def test_update(self, client: TestClient) -> None:
        project = make_project(client)
        resp = client.put(
            f"/api/projects/{project['id']}",
            json={"name": "новое-имя", "description": "новое-описание"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "новое-имя"

    def test_get_missing_404(self, client: TestClient) -> None:
        assert client.get("/api/projects/999").status_code == 404

    def test_delete(self, client: TestClient) -> None:
        project = make_project(client)
        assert client.delete(f"/api/projects/{project['id']}").status_code == 204
        assert client.get(f"/api/projects/{project['id']}").status_code == 404

    def test_delete_with_comparison_409(self, client: TestClient) -> None:
        project = make_project(client)
        make_comparison(client, project["id"])
        resp = client.delete(f"/api/projects/{project['id']}")
        assert resp.status_code == 409


class TestComparisons:
    def test_create_and_diffs(self, client: TestClient) -> None:
        project = make_project(client)
        comparison = make_comparison(client, project["id"])
        assert comparison["status"] == "DONE"
        assert [s["role"] for s in comparison["schemas"]] == ["source", "target"]
        diffs = {d["object_name"]: d for d in comparison["diffs"]}
        assert diffs["payments"]["diff_type"] == "ADDED"
        assert diffs["payments"]["color"] == "green"
        assert diffs["full_name"]["path"] == "users.full_name"
        assert diffs["name"]["diff_type"] == "REMOVED"
        assert diffs["name"]["color"] == "red"

    def test_strategy_table_only(self, client: TestClient) -> None:
        project = make_project(client)
        comparison = make_comparison(client, project["id"], strategy="table")
        assert {d["object_type"] for d in comparison["diffs"]} == {"table"}

    def test_bad_ddl_422_with_line(self, client: TestClient) -> None:
        project = make_project(client)
        resp = client.post(
            "/api/comparisons",
            json={
                "project_id": project["id"],
                "name": "bad",
                "dialect": "postgresql",
                "source_ddl": "\n\nCREATE TABLE broken (",
                "target_ddl": TGT_DDL,
            },
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["line"] == 3

    def test_empty_ddl_422(self, client: TestClient) -> None:
        project = make_project(client)
        resp = client.post(
            "/api/comparisons",
            json={
                "project_id": project["id"],
                "name": "empty",
                "dialect": "postgresql",
                "source_ddl": "",
                "target_ddl": TGT_DDL,
            },
        )
        assert resp.status_code == 422

    def test_missing_project_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/comparisons",
            json={
                "project_id": 999,
                "name": "cmp",
                "dialect": "postgresql",
                "source_ddl": SRC_DDL,
                "target_ddl": TGT_DDL,
            },
        )
        assert resp.status_code == 404

    def test_get_missing_404(self, client: TestClient) -> None:
        assert client.get("/api/comparisons/999").status_code == 404

    def test_validate_ok(self, client: TestClient) -> None:
        project = make_project(client)
        comparison = make_comparison(client, project["id"])
        resp = client.post(f"/api/comparisons/{comparison['id']}/validate")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "errors": []}

    def test_validate_missing_404(self, client: TestClient) -> None:
        assert client.post("/api/comparisons/999/validate").status_code == 404


class TestMigrations:
    def test_create_and_export(self, client: TestClient) -> None:
        project = make_project(client)
        comparison = make_comparison(client, project["id"])
        resp = client.post("/api/migrations", json={"comparison_id": comparison["id"]})
        assert resp.status_code == 201
        migration = resp.json()
        assert migration["operation_count"] > 0
        assert migration["script"]["version"] == "v1"

        resp = client.get(f"/api/migrations/{migration['id']}/export")
        assert resp.status_code == 200
        assert "CREATE TABLE" in resp.text
        assert "attachment" in resp.headers["content-disposition"]

    def test_no_diffs_422(self, client: TestClient) -> None:
        project = make_project(client)
        comparison = make_comparison(
            client, project["id"], source_ddl=SRC_DDL, target_ddl=SRC_DDL
        )
        assert comparison["diffs"] == []
        resp = client.post("/api/migrations", json={"comparison_id": comparison["id"]})
        assert resp.status_code == 422

    def test_missing_comparison_404(self, client: TestClient) -> None:
        assert client.post("/api/migrations", json={"comparison_id": 999}).status_code == 404

    def test_export_missing_404(self, client: TestClient) -> None:
        assert client.get("/api/migrations/999/export").status_code == 404
