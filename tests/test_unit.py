"""Модульные тесты ЛР № 4 (промпты 4.1, 4.1.1–4.1.3): 10 тестов REST API СМД.

Группы сценариев:
- успешные (4.1.1): CRUD проектов, сравнение с подсветкой, миграция и экспорт, validate;
- ошибочные (4.1.2): пустое имя, несуществующий идентификатор, дубликат, неверный тип;
- граничные (4.1.3): максимальная длина имени, специальные символы, объёмный DDL.

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

BOUNDARY_DDL = "\n".join(
    f"CREATE TABLE table_{i:02d} (id SERIAL PRIMARY KEY, amount INTEGER NOT NULL);"
    for i in range(30)
)


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


class TestSuccessfulScenarios:
    """Промпт 4.1.1: успешные CRUD-сценарии, коды ответов и содержимое."""

    def test_project_crud_cycle(self, client: TestClient) -> None:
        # создание -> чтение -> обновление -> удаление проекта
        created = make_project(client, "crud-проект")
        assert created["name"] == "crud-проект"
        assert created["description"] == "тест"

        read = client.get(f"/api/projects/{created['id']}")
        assert read.status_code == 200
        assert read.json()["name"] == "crud-проект"

        updated = client.put(
            f"/api/projects/{created['id']}", json={"description": "обновлено"}
        )
        assert updated.status_code == 200
        assert updated.json()["description"] == "обновлено"

        deleted = client.delete(f"/api/projects/{created['id']}")
        assert deleted.status_code == 204
        assert client.get(f"/api/projects/{created['id']}").status_code == 404

    def test_comparison_diffs_with_colors(self, client: TestClient) -> None:
        # Т1 + Т2: различия содержат пути и цветовую подсветку
        project = make_project(client)
        comparison = make_comparison(client, project["id"])
        assert comparison["status"] == "DONE"
        diffs = {d["object_name"]: d for d in comparison["diffs"]}
        assert diffs["payments"]["diff_type"] == "ADDED"
        assert diffs["payments"]["color"] == "green"
        assert diffs["full_name"]["path"] == "users.full_name"
        assert diffs["full_name"]["diff_type"] == "ADDED"
        assert diffs["full_name"]["color"] == "green"
        assert diffs["name"]["diff_type"] == "REMOVED"
        assert diffs["name"]["color"] == "red"
        assert diffs["email"]["diff_type"] == "MODIFIED"
        assert diffs["email"]["color"] == "yellow"

    def test_migration_generation_and_export(self, client: TestClient) -> None:
        # Т3: генерация миграции и экспорт SQL-скрипта с проверкой содержимого
        project = make_project(client)
        comparison = make_comparison(client, project["id"])
        created = client.post("/api/migrations", json={"comparison_id": comparison["id"]})
        assert created.status_code == 201
        migration = created.json()
        assert migration["operation_count"] > 0
        assert migration["script"]["version"] == "v1"
        assert migration["script"]["is_applied"] is False

        exported = client.get(f"/api/migrations/{migration['id']}/export")
        assert exported.status_code == 200
        assert "CREATE TABLE" in exported.text
        assert "ALTER TABLE" in exported.text
        assert 'filename="migration_v1.sql"' in exported.headers["content-disposition"]

    def test_validate_invariants_ok(self, client: TestClient) -> None:
        # POST /validate: инварианты агрегата Comparison выполнены, ошибок нет
        project = make_project(client)
        comparison = make_comparison(client, project["id"])
        resp = client.post(f"/api/comparisons/{comparison['id']}/validate")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "errors": []}


class TestErrorScenarios:
    """Промпт 4.1.2: пустое имя, несуществующий идентификатор, дубликат, неверный тип."""

    def test_blank_name_422(self, client: TestClient) -> None:
        # пустое имя и имя из пробелов отклоняются валидацией Pydantic
        assert client.post("/api/projects", json={"name": ""}).status_code == 422
        assert client.post("/api/projects", json={"name": "   "}).status_code == 422

    def test_unknown_ids_404(self, client: TestClient) -> None:
        # несуществующие идентификаторы проекта, сравнения, миграции и скрипта
        assert client.get("/api/projects/999").status_code == 404
        assert client.get("/api/comparisons/999").status_code == 404
        assert client.post("/api/migrations", json={"comparison_id": 999}).status_code == 404
        assert client.get("/api/migrations/999/export").status_code == 404

    def test_duplicate_name_409_and_wrong_dialect_422(self, client: TestClient) -> None:
        # дубликат имени проекта -> 409; неверный диалект (не из перечисления) -> 422
        make_project(client, "дубликат")
        assert (
            client.post("/api/projects", json={"name": "дубликат"}).status_code == 409
        )
        project = make_project(client, "диалект")
        resp = client.post(
            "/api/comparisons",
            json={
                "project_id": project["id"],
                "name": "cmp",
                "dialect": "oracle",
                "source_ddl": SRC_DDL,
                "target_ddl": TGT_DDL,
            },
        )
        assert resp.status_code == 422


class TestBoundaryCases:
    """Промпт 4.1.3: граничные значения длины имени, спецсимволы, объёмный DDL."""

    def test_name_length_boundaries(self, client: TestClient) -> None:
        # граница поля: имя ровно 100 символов принимается, 101 — отклоняется
        name_100 = "и" * 100
        created = make_project(client, name_100)
        assert created["name"] == name_100
        assert client.post("/api/projects", json={"name": "и" * 101}).status_code == 422

    def test_special_characters_in_name(self, client: TestClient) -> None:
        # специальные символы и юникод сохраняются и читаются без искажений
        name = "проект <>&'\"%20 ✓ 🗂"
        created = make_project(client, name)
        read = client.get(f"/api/projects/{created['id']}")
        assert read.status_code == 200
        assert read.json()["name"] == name

    def test_large_ddl_30_tables(self, client: TestClient) -> None:
        # граничный объём: DDL из 30 таблиц обрабатывается, все различия учтены
        project = make_project(client, "большая-схема")
        comparison = make_comparison(
            client, project["id"], source_ddl=BOUNDARY_DDL, target_ddl=BOUNDARY_DDL
        )
        assert comparison["status"] == "DONE"
        assert comparison["diffs"] == []
        # та же схема без одной таблицы даёт одно REMOVED-различие
        dropped = BOUNDARY_DDL.rsplit("\n", 1)[0]
        comparison = make_comparison(
            client, project["id"], name="cmp-drop", source_ddl=BOUNDARY_DDL, target_ddl=dropped
        )
        removed = [d for d in comparison["diffs"] if d["diff_type"] == "REMOVED"]
        assert len(removed) == 1
        assert removed[0]["object_type"] == "table"
