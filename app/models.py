"""Модели SQLAlchemy — перенос классов домена из ЛР № 2.

Соответствие классам ЛР № 2: Project, Schema, Table, Column (здесь TableColumn),
Comparison, Diff, Migration, MigrationScript. Класс TableColumn назван иначе,
чтобы не пересекаться с sqlalchemy.Column.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """Проект сравнения — корень агрегата АГ-1 (ЛР № 2)."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    comparisons: Mapped[list["Comparison"]] = relationship(back_populates="project")


class Comparison(Base):
    """Сеанс сравнения двух схем — корень агрегата АГ-2 (ЛР № 2)."""

    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    dialect: Mapped[str] = mapped_column(String(20))  # postgresql | mysql
    strategy: Mapped[str] = mapped_column(String(20), default="column")  # table | column
    status: Mapped[str] = mapped_column(String(10), default="DONE")  # RUNNING | DONE | FAILED
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="comparisons")
    schemas: Mapped[list["Schema"]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan"
    )
    diffs: Mapped[list["Diff"]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan"
    )
    migrations: Mapped[list["Migration"]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan"
    )


class Schema(Base):
    """Схема базы данных (роль source или target) — класс Schema (ЛР № 2)."""

    __tablename__ = "schemas"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(6))  # source | target
    name: Mapped[str] = mapped_column(String(100))
    dialect: Mapped[str] = mapped_column(String(20))

    comparison: Mapped["Comparison"] = relationship(back_populates="schemas")
    tables: Mapped[list["Table"]] = relationship(
        back_populates="schema", cascade="all, delete-orphan"
    )


class Table(Base):
    """Таблица схемы — класс Table (ЛР № 2)."""

    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_id: Mapped[int] = mapped_column(ForeignKey("schemas.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    schema: Mapped["Schema"] = relationship(back_populates="tables")
    columns: Mapped[list["TableColumn"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )


class TableColumn(Base):
    """Колонка таблицы — класс Column (ЛР № 2)."""

    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    data_type: Mapped[str] = mapped_column(String(50), default="TEXT")
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_pk: Mapped[bool] = mapped_column(Boolean, default=False)

    table: Mapped["Table"] = relationship(back_populates="columns")


DIFF_COLORS: dict[str, str] = {
    "ADDED": "green",
    "REMOVED": "red",
    "MODIFIED": "yellow",
}


class Diff(Base):
    """Одно выявленное различие — класс Diff (ЛР № 2), тип определяет подсветку (Т2)."""

    __tablename__ = "diffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id", ondelete="CASCADE"), index=True
    )
    object_type: Mapped[str] = mapped_column(String(10))  # table | column
    object_name: Mapped[str] = mapped_column(String(100))
    path: Mapped[str] = mapped_column(String(300))  # адрес объекта: таблица/колонка
    diff_type: Mapped[str] = mapped_column(String(10))  # ADDED | REMOVED | MODIFIED
    details: Mapped[dict | None] = mapped_column(JSON, default=None)

    comparison: Mapped["Comparison"] = relationship(back_populates="diffs")

    @property
    def color(self) -> str:
        """Цвет подсветки различия (Т2): зелёный — добавлено, красный — удалено,
        жёлтый — изменено."""
        return DIFF_COLORS.get(self.diff_type, "gray")


class Migration(Base):
    """Набор операций миграции — класс Migration (ЛР № 2)."""

    __tablename__ = "migrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(10), default="forward")
    operation_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    comparison: Mapped["Comparison"] = relationship(back_populates="migrations")
    script: Mapped["MigrationScript"] = relationship(
        back_populates="migration", cascade="all, delete-orphan", uselist=False
    )


class MigrationScript(Base):
    """Скрипт миграции с версионированием — корень агрегата АГ-3 (ЛР № 2).

    Инвариант ЛР № 2: после is_applied = True скрипт неизменяем.
    """

    __tablename__ = "migration_scripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    migration_id: Mapped[int] = mapped_column(
        ForeignKey("migrations.id", ondelete="CASCADE"), index=True, unique=True
    )
    sql: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(20), default="sql")
    version: Mapped[str] = mapped_column(String(10), default="v1")
    is_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    migration: Mapped["Migration"] = relationship(back_populates="script")
