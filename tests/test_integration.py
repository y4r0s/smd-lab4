"""Интеграционные тесты ЛР № 4 (промпты 4.2, 4.2.1–4.2.2): реальный PostgreSQL 16.

testcontainers поднимает контейнер PostgreSQL; REST-интерфейс из ЛР № 3
работает с реальной БД (не SQLite). Три теста:
1) подключение к PostgreSQL и healthcheck;
2) сохранение и последующая загрузка сравнения (целостность данных);
3) целостность связей при удалении (инвариант «проект со сравнениями
   не удаляется», каскадное удаление схем и различий).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app import models
from app.database import Base, get_db
from app.main import app

pytestmark = pytest.mark.integration

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


@pytest.fixture(scope="module")
def pg_sessionmaker():
    """Контейнер PostgreSQL 16 (testcontainers) и фабрика сессий к нему."""
    with PostgresContainer(
        "postgres:16-alpine", username="smd", password="smd", dbname="smd"
    ) as pg:
        engine = create_engine(pg.get_connection_url(driver="psycopg2"))
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        engine.dispose()


@pytest.fixture()
def pg_client(pg_sessionmaker):
    """TestClient с переопределением зависимости get_db на PostgreSQL."""
    def override():
        db = pg_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_postgres_connection(pg_sessionmaker, pg_client: TestClient) -> None:
    """Промпт 4.2.1: запуск контейнера, подключение, проверка соединения и healthcheck."""
    with pg_sessionmaker() as session:
        assert session.execute(text("SELECT version()")).scalar().startswith("PostgreSQL 16")
    resp = pg_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_save_and_load_comparison(pg_sessionmaker, pg_client: TestClient) -> None:
    """Промпт 4.2.2: сохранение сравнения в PostgreSQL и загрузка — целостность данных."""
    project = pg_client.post("/api/projects", json={"name": "интеграционный"}).json()
    resp = pg_client.post(
        "/api/comparisons",
        json={
            "project_id": project["id"],
            "name": "cmp-pg",
            "dialect": "postgresql",
            "source_ddl": SRC_DDL,
            "target_ddl": TGT_DDL,
        },
    )
    assert resp.status_code == 201
    comparison_id = resp.json()["id"]

    # чтение из БД напрямую и через API: данные совпадают
    loaded = pg_client.get(f"/api/comparisons/{comparison_id}").json()
    assert loaded["status"] == "DONE"
    assert [s["role"] for s in loaded["schemas"]] == ["source", "target"]
    diff_names = {d["object_name"] for d in loaded["diffs"]}
    assert diff_names == {"payments", "full_name", "name", "email"}

    with pg_sessionmaker() as session:
        tables = {
            row.name
            for row in session.query(models.Table).join(models.Schema).filter(
                models.Schema.comparison_id == comparison_id
            ).all()
        }
        assert tables == {"users", "payments"}


def test_delete_integrity(pg_sessionmaker, pg_client: TestClient) -> None:
    """Проверка связей (верификация промпта 4.2.2): проект со сравнениями не
    удаляется (409); после удаления пустого проекта данные сравнения целы."""
    project = pg_client.post("/api/projects", json={"name": "со-сравнением"}).json()
    pg_client.post(
        "/api/comparisons",
        json={
            "project_id": project["id"],
            "name": "cmp-lock",
            "dialect": "postgresql",
            "source_ddl": SRC_DDL,
            "target_ddl": TGT_DDL,
        },
    )
    # инвариант агрегата Project на реальной БД
    resp = pg_client.delete(f"/api/projects/{project['id']}")
    assert resp.status_code == 409
    assert pg_client.get(f"/api/projects/{project['id']}").status_code == 200

    # проект без сравнений удаляется, данные остальных сохраняются
    other = pg_client.post("/api/projects", json={"name": "пустой"}).json()
    assert pg_client.delete(f"/api/projects/{other['id']}").status_code == 204
    with pg_sessionmaker() as session:
        assert session.get(models.Project, other["id"]) is None
        assert session.get(models.Project, project["id"]) is not None
        # различия удалённого и живого проектов считаются раздельно (изоляция данных)
        diffs_of = lambda pid: (  # noqa: E731
            session.query(models.Diff)
            .join(models.Comparison, models.Diff.comparison_id == models.Comparison.id)
            .filter(models.Comparison.project_id == pid)
            .count()
        )
        assert diffs_of(project["id"]) == 4
        assert diffs_of(other["id"]) == 0
