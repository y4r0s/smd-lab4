"""Pydantic-схемы: валидация входных данных и сериализация ответов.

Инварианты агрегатов ЛР № 2 (таблица 11) проверяются здесь:
уникальность имени проекта (на маршруте, 409), непустые имена,
перечисление DiffType — основа цветовой подсветки (Т2).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Dialect = Literal["postgresql", "mysql"]
StrategyName = Literal["table", "column"]
DiffTypeName = Literal["ADDED", "REMOVED", "MODIFIED"]


def _clean_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("имя не может быть пустым или состоять из пробелов")
    return name


class ProjectCreate(BaseModel):
    """Создание проекта (ФТ-1)."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        return _clean_name(value)


class ProjectUpdate(BaseModel):
    """Обновление проекта."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class ComparisonCreate(BaseModel):
    """Создание сравнения: две схемы задаются DDL-скриптами (ФТ-2)."""

    project_id: int
    name: str = Field(min_length=1, max_length=100)
    dialect: Dialect
    strategy: StrategyName = "column"
    source_ddl: str = Field(min_length=1, description="DDL-скрипт схемы-источника")
    target_ddl: str = Field(min_length=1, description="DDL-скрипт схемы-цели")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        return _clean_name(value)


class DiffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_type: str
    object_name: str
    path: str
    diff_type: DiffTypeName
    color: str
    details: dict | None = None


class SchemaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["source", "target"]
    name: str
    dialect: Dialect


class ComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    dialect: Dialect
    strategy: StrategyName
    status: Literal["RUNNING", "DONE", "FAILED"]
    error: str | None = None
    created_at: datetime
    schemas: list[SchemaOut] = []
    diffs: list[DiffOut] = []


class ValidateOut(BaseModel):
    """Результат проверки инвариантов сравнения (POST /comparisons/{id}/validate)."""

    ok: bool
    errors: list[str] = []


class MigrationCreate(BaseModel):
    """Генерация скрипта миграции по результатам сравнения (Т3)."""

    comparison_id: int


class MigrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    comparison_id: int
    direction: Literal["forward"]
    operation_count: int
    created_at: datetime
    script: "MigrationScriptOut | None" = None


class MigrationScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sql: str
    format: str
    version: str
    is_applied: bool


MigrationOut.model_rebuild()


class HealthOut(BaseModel):
    status: str
    database: str
