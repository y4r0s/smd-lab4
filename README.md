# СМД API — Средство моделирования данных (вариант № 23)

REST-интерфейс инструмента сравнения схем БД и генерации миграционных скриптов,
тестирование (pytest, testcontainers) и мониторинг (Prometheus, Grafana).
ЛР № 4 по дисциплине «Технологии разработки программных средств» (МГТУ «СТАНКИН»).

Стек: Python 3.12, FastAPI, SQLAlchemy 2.x, PostgreSQL 16, Docker, pytest,
testcontainers, prometheus-client, Prometheus, Grafana, GitHub Actions.

## Запуск

```bash
docker compose up --build
# Swagger UI: http://localhost:8000/docs
# Healthcheck: http://localhost:8000/api/health
# Метрики: http://localhost:8000/metrics
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin, дашборд «СМД — мониторинг»)
```

Без Docker (нужен PostgreSQL, переменная `DATABASE_URL`):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Тесты

10 модульных тестов (успешные, ошибочные и граничные сценарии) и 3 интеграционных
теста с testcontainers (реальный PostgreSQL 16, требуется Docker):

```bash
pip install -r requirements-dev.txt
pytest                        # весь набор
pytest -m integration         # только интеграционные (testcontainers)
pytest -m "not integration"   # только модульные
```

## Мониторинг

Сбор метрик — prometheus-client; экспорт — маршрут `/metrics` (скрейпинг каждые 5 с).
Бизнес-метрики: `smd_projects_total`, `smd_comparisons_total`,
`smd_comparison_duration_seconds`, `smd_export_duration_seconds`;
HTTP-метрики: `smd_http_requests_total`, `smd_http_request_duration_seconds`.
Панель Grafana (4 графика): активность пользователей, время отклика (p95),
топ ошибок, время сравнения схем и экспорта миграций.

## Конечные точки (13)

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
| 13 | `GET /metrics` | экспорт метрик Prometheus (ЛР № 4) |
