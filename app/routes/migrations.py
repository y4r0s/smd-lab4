"""Маршруты миграций (Т3): генерация и экспорт скрипта миграции.

Инвариант агрегата MigrationScript (ЛР № 2): после is_applied = True
скрипт неизменяем — в API нет маршрута изменения скрипта.
"""
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..metrics import EXPORT_DURATION
from ..services.diff_engine import DiffItem
from ..services.migration_generator import generate_sql

router = APIRouter(prefix="/migrations", tags=["migrations"])


def _to_items(diffs: list[models.Diff]) -> list[DiffItem]:
    return [
        DiffItem(
            object_type=d.object_type,
            object_name=d.object_name,
            path=d.path,
            diff_type=d.diff_type,
            details=d.details or {},
        )
        for d in diffs
    ]


@router.post("", response_model=schemas.MigrationOut, status_code=status.HTTP_201_CREATED)
def create_migration(
    payload: schemas.MigrationCreate, db: Session = Depends(get_db)
) -> models.Migration:
    comparison = db.get(models.Comparison, payload.comparison_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="сравнение не найдено")
    if comparison.status != "DONE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="сравнение не завершено (статус DONE)"
        )
    if not comparison.diffs:
        raise HTTPException(
            status_code=422,
            detail="различий нет — мигрировать нечего",
        )
    statements = generate_sql(_to_items(comparison.diffs), comparison.dialect)
    migration = models.Migration(comparison_id=comparison.id, operation_count=len(statements))
    db.add(migration)
    db.flush()
    db.add(models.MigrationScript(migration_id=migration.id, sql="\n".join(statements)))
    db.commit()
    db.refresh(migration)
    return migration


@router.get("/{migration_id}", response_model=schemas.MigrationOut)
def get_migration(migration_id: int, db: Session = Depends(get_db)) -> models.Migration:
    migration = db.get(models.Migration, migration_id)
    if migration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="миграция не найдена")
    return migration


@router.get("/{migration_id}/export", response_class=PlainTextResponse)
def export_script(migration_id: int, db: Session = Depends(get_db)) -> PlainTextResponse:
    """Экспорт SQL-скрипта миграции (методы preview()/export() класса MigrationScript, ЛР № 2)."""
    started = time.perf_counter()
    migration = db.get(models.Migration, migration_id)
    if migration is None or migration.script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="скрипт миграции не найден"
        )
    filename = f"migration_{migration.script.version}.sql"
    EXPORT_DURATION.observe(time.perf_counter() - started)
    return PlainTextResponse(
        content=migration.script.sql,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
