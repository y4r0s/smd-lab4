# СМД API — Средство моделирования данных (вариант № 23)

REST-интерфейс инструмента сравнения схем БД и генерации миграционных скриптов.
ЛР № 3 по дисциплине «Технологии разработки программных средств» (МГТУ «СТАНКИН»).

Стек: Python 3.10+, FastAPI, SQLAlchemy 2.x, PostgreSQL 16, Docker, GitHub Actions.

## Запуск

```bash
docker compose up --build
# Swagger UI: http://localhost:8000/docs
# Healthcheck: http://localhost:8000/api/health
```

Без Docker (нужен PostgreSQL, переменная `DATABASE_URL`):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Тесты

```bash
pip install -r requirements-dev.txt
pytest
```

## Конечные точки (12)

| № | Метод и путь | Назначение |
|---|---|---|
| 1 | `GET /api/health` | проверка работоспособности приложения и БД (healthcheck) |
| 2 | `POST /api/projects` | создать проект сравнения |
| 3 | `GET /api/projects` | список проектов |
| 4 | `GET /api/projects/{id}` | получить проект (404 при отсутствии) |
| 5 | `PUT /api/projects/{id}` | обновить проект |
| 6 | `DELETE /api/projects/{id}` | удалить проект (409 при наличии сравнений) |
| 7 | `POST /api/comparisons` | создать сравнение: разбор DDL, сравнение схем, сохранение различий |
| 8 | `GET /api/comparisons/{id}` | получить сравнение со схемами и различиями |
| 9 | `POST /api/comparisons/{id}/validate` | проверить инварианты агрегата Comparison |
| 10 | `POST /api/migrations` | сгенерировать скрипт миграции по различиям |
| 11 | `GET /api/migrations/{id}` | получить миграцию со скриптом |
| 12 | `GET /api/migrations/{id}/export` | экспорт SQL-скрипта (файл) |

