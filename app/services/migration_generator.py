"""MigrationGenerator — генерация скриптов миграции (сервисный класс ЛР № 2).

Шаблон «Фабрика» (ЛР № 2, таблица 8): выбор диалекта SQL (PostgreSQL / MySQL).
"""
from .diff_engine import DiffItem

_MYSQL_TYPES = {"SERIAL": "INT AUTO_INCREMENT", "BIGSERIAL": "BIGINT AUTO_INCREMENT"}


def _quote(name: str, dialect: str) -> str:
    return f"`{name}`" if dialect == "mysql" else f'"{name}"'


def _column_def(col: dict, dialect: str) -> str:
    """Определение колонки для CREATE TABLE / ADD / MODIFY COLUMN."""
    data_type = col.get("data_type", "TEXT")
    if dialect == "mysql":
        data_type = _MYSQL_TYPES.get(data_type, data_type)
    parts = [f"{_quote(col.get('name', 'col'), dialect)} {data_type}"]
    if not col.get("nullable", True):
        parts.append("NOT NULL")
    if col.get("is_pk"):
        parts.append("PRIMARY KEY")
    return " ".join(parts)


def _create_table(diff: DiffItem, dialect: str) -> str:
    columns = (diff.details or {}).get("columns", [])
    defs = ", ".join(_column_def(c, dialect) for c in columns) or "id INTEGER PRIMARY KEY"
    return f"CREATE TABLE {_quote(diff.object_name, dialect)} ({defs});"


def _drop_table(diff: DiffItem, dialect: str) -> str:
    cascade = " CASCADE" if dialect == "postgresql" else ""
    return f"DROP TABLE IF EXISTS {_quote(diff.object_name, dialect)}{cascade};"


def _add_column(diff: DiffItem, dialect: str) -> str:
    table, column = diff.path.split(".", 1)
    col_def = _column_def({"name": column, **(diff.details or {})}, dialect)
    return f"ALTER TABLE {_quote(table, dialect)} ADD COLUMN {col_def};"


def _drop_column(diff: DiffItem, dialect: str) -> str:
    table, column = diff.path.split(".", 1)
    return f"ALTER TABLE {_quote(table, dialect)} DROP COLUMN {_quote(column, dialect)};"


def _alter_column(diff: DiffItem, dialect: str) -> list[str]:
    """Изменение колонки: в PostgreSQL тип и NULL-модификатор меняются отдельно."""
    table, column = diff.path.split(".", 1)
    after = (diff.details or {}).get("after", {})
    if dialect == "mysql":
        col_def = _column_def({"name": column, **after}, dialect)
        return [f"ALTER TABLE {_quote(table, dialect)} MODIFY COLUMN {col_def};"]
    statements = [
        f"ALTER TABLE {_quote(table, dialect)} "
        f"ALTER COLUMN {_quote(column, dialect)} TYPE {after.get('data_type', 'TEXT')};"
    ]
    if not after.get("nullable", True):
        statements.append(
            f"ALTER TABLE {_quote(table, dialect)} "
            f"ALTER COLUMN {_quote(column, dialect)} SET NOT NULL;"
        )
    return statements


SUPPORTED_DIALECTS = ("postgresql", "mysql")


def generate_sql(diffs: list[DiffItem], dialect: str) -> list[str]:
    """Сгенерировать список SQL-операторов миграции (direction: forward).

    Фабрика диалектов: PostgreSQL и MySQL дают разные операторы
    (DROP ... CASCADE, ALTER/MODIFY COLUMN, AUTO_INCREMENT).
    """
    if dialect not in SUPPORTED_DIALECTS:
        raise ValueError(f"неподдерживаемый SQL-диалект: {dialect!r}")
    statements: list[str] = []
    for diff in diffs:
        kind = (diff.object_type, diff.diff_type)
        if kind == ("table", "ADDED"):
            statements.append(_create_table(diff, dialect))
        elif kind == ("table", "REMOVED"):
            statements.append(_drop_table(diff, dialect))
        elif kind == ("column", "ADDED"):
            statements.append(_add_column(diff, dialect))
        elif kind == ("column", "REMOVED"):
            statements.append(_drop_column(diff, dialect))
        elif kind == ("column", "MODIFIED"):
            statements.extend(_alter_column(diff, dialect))
    return statements
