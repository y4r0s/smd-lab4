"""Маршруты сравнения схем (Т1, Т2).

Создание сравнения повторяет ключевой сценарий ЛР № 2 (рис. 4):
разбор DDL (DdlParser) -> сравнение (DiffEngine, «Стратегия»)
-> сохранение различий Diff[] в БД.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.ddl_parser import DdlParseError, ParsedTable, parse_ddl
from ..services.diff_engine import get_strategy

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _save_schema(
    db: Session, comparison: models.Comparison, role: str, tables: list[ParsedTable]
) -> models.Schema:
    schema = models.Schema(
        comparison_id=comparison.id,
        role=role,
        name=f"{comparison.name}_{role}",
        dialect=comparison.dialect,
    )
    db.add(schema)
    db.flush()
    for table in tables:
        row = models.Table(schema_id=schema.id, name=table.name, order_index=table.order_index)
        db.add(row)
        db.flush()
        for col in table.columns:
            db.add(
                models.TableColumn(
                    table_id=row.id,
                    name=col.name,
                    data_type=col.data_type,
                    nullable=col.nullable,
                    is_pk=col.is_pk,
                )
            )
    return schema


@router.post("", response_model=schemas.ComparisonOut, status_code=status.HTTP_201_CREATED)
def create_comparison(
    payload: schemas.ComparisonCreate, db: Session = Depends(get_db)
) -> models.Comparison:
    project = db.get(models.Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="проект не найден")
    try:
        source_tables = parse_ddl(payload.source_ddl)
        target_tables = parse_ddl(payload.target_ddl)
    except DdlParseError as exc:
        # Альтернативный поток ЛР № 2 (рис. 5): ошибка парсинга DDL -> 422 с номером строки.
        raise HTTPException(
            status_code=422,
            detail={"message": f"ошибка разбора DDL: {exc.message}", "line": exc.line_no},
        ) from exc

    comparison = models.Comparison(
        project_id=payload.project_id,
        name=payload.name,
        dialect=payload.dialect,
        strategy=payload.strategy,
        status="DONE",
    )
    db.add(comparison)
    db.flush()

    _save_schema(db, comparison, "source", source_tables)
    _save_schema(db, comparison, "target", target_tables)

    for item in get_strategy(payload.strategy).compare(source_tables, target_tables):
        db.add(
            models.Diff(
                comparison_id=comparison.id,
                object_type=item.object_type,
                object_name=item.object_name,
                path=item.path,
                diff_type=item.diff_type,
                details=item.details,
            )
        )
    db.commit()
    db.refresh(comparison)
    return comparison


@router.get("/{comparison_id}", response_model=schemas.ComparisonOut)
def get_comparison(comparison_id: int, db: Session = Depends(get_db)) -> models.Comparison:
    comparison = db.get(models.Comparison, comparison_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="сравнение не найдено")
    return comparison


@router.post("/{comparison_id}/validate", response_model=schemas.ValidateOut)
def validate_comparison(comparison_id: int, db: Session = Depends(get_db)) -> schemas.ValidateOut:
    """Проверка инвариантов агрегата Comparison (ЛР № 2, таблица 11)."""
    comparison = db.get(models.Comparison, comparison_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="сравнение не найдено")
    errors: list[str] = []
    roles = {schema.role for schema in comparison.schemas}
    if roles != {"source", "target"}:
        errors.append("у сравнения должны быть схемы source и target")
    dialects = {schema.dialect for schema in comparison.schemas}
    if len(dialects) > 1:
        errors.append("сравниваются схемы разных диалектов (инвариант ЛР № 2)")
    for diff in comparison.diffs:
        if diff.comparison_id != comparison.id:
            errors.append(f"различие {diff.id} ссылается на другое сравнение")
    if comparison.status not in {"DONE", "FAILED"}:
        errors.append(f"неизвестный статус сравнения: {comparison.status!r}")
    return schemas.ValidateOut(ok=not errors, errors=errors)
