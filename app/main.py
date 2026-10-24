"""Точка входа FastAPI: приложение, маршруты, проверка работоспособности, /metrics."""
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .metrics import HTTP_REQUESTS, HTTP_REQUEST_DURATION
from .routes import comparisons, migrations, projects

# служебные маршруты, не учитываемые в HTTP-метриках (healthcheck compose и скрейпинг)
_SKIPPED_PATHS = {"/metrics", "/api/health"}


async def metrics_middleware(request: Request, call_next):
    """HTTP-метрики: счётчик запросов и длительность обработки (для панели Grafana)."""
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path not in _SKIPPED_PATHS:
        route = request.scope.get("route")
        endpoint = route.path if route is not None else request.url.path
        HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
        HTTP_REQUEST_DURATION.labels(request.method, endpoint).observe(
            time.perf_counter() - start
        )
    return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="СМД API",
    description=(
        "REST-интерфейс инструмента «Средство моделирования данных» (вариант № 23): "
        "проекты сравнения, сравнение схем БД, генерация скриптов миграции."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.middleware("http")(metrics_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 12 конечных точек ЛР № 3 (CRUD, сравнения, миграции, health) + /metrics (ЛР № 4).
app.include_router(projects.router, prefix="/api")
app.include_router(comparisons.router, prefix="/api")
app.include_router(migrations.router, prefix="/api")


@app.get("/metrics", tags=["monitoring"])
def metrics() -> Response:
    """Экспорт метрик Prometheus (prometheus-client)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> JSONResponse:
    """Проверка работоспособности: доступность приложения и БД (для healthcheck)."""
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:  # noqa: BLE001 - healthcheck обязан пережить недоступность БД
        database_status = "unavailable"
    status_code = 200 if database_status == "ok" else 503
    return JSONResponse(
        status_code=status_code, content={"status": "ok", "database": database_status}
    )
