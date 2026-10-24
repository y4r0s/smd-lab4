"""DdlParser — разбор DDL-скриптов (сервисный класс ЛР № 2).

Поддерживаются операторы CREATE TABLE диалектов PostgreSQL и MySQL.
Ошибки разбора возвращают номер строки (альтернативный поток ЛР № 2, рис. 5).
"""
import re
from dataclasses import dataclass, field

_CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?(\w+)[\"'`\]]?\s*\(",
    re.IGNORECASE,
)
_SKIP_PREFIXES = ("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CONSTRAINT", "KEY", "INDEX", "CHECK")
_IDENT_RE = re.compile(r"[\"'`\[]?(\w+)[\"'`\]]?")
_TYPE_RE = re.compile(r"^\w+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?")


@dataclass
class ParsedColumn:
    """Колонка после разбора DDL."""

    name: str
    data_type: str
    nullable: bool = True
    is_pk: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "nullable": self.nullable,
            "is_pk": self.is_pk,
        }


@dataclass
class ParsedTable:
    """Таблица после разбора DDL."""

    name: str
    columns: list[ParsedColumn] = field(default_factory=list)
    order_index: int = 0


class DdlParseError(ValueError):
    """Ошибка разбора DDL с номером строки."""

    def __init__(self, message: str, line_no: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line_no = line_no


def _line_of(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", text)


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _parse_column(line: str, line_no: int) -> ParsedColumn:
    stripped = line.strip().rstrip(",")
    match = _IDENT_RE.match(stripped)
    if not match:
        raise DdlParseError(f"не удалось разобрать определение колонки: {stripped!r}", line_no)
    name = match.group(1)
    rest = stripped[match.end() :].strip()
    type_match = _TYPE_RE.match(rest)
    data_type = type_match.group(0).replace(" ", "").upper() if type_match else "TEXT"
    upper = rest.upper()
    is_pk = "PRIMARY KEY" in upper
    return ParsedColumn(
        name=name,
        data_type=data_type,
        nullable="NOT NULL" not in upper and not is_pk,
        is_pk=is_pk,
    )


def parse_ddl(ddl_text: str) -> list[ParsedTable]:
    """Разобрать DDL-скрипт в список таблиц. Бросает DdlParseError с номером строки."""
    if not ddl_text or not ddl_text.strip():
        raise DdlParseError("DDL-скрипт пуст", 1)
    text = _strip_comments(ddl_text)
    tables: list[ParsedTable] = []
    for create in _CREATE_RE.finditer(text):
        line_no = _line_of(text, create.start())
        depth = 1
        pos = create.end()
        while pos < len(text) and depth > 0:
            if text[pos] == "(":
                depth += 1
            elif text[pos] == ")":
                depth -= 1
            pos += 1
        if depth != 0:
            raise DdlParseError("незакрытая скобка в определении таблицы", line_no)
        body = text[create.end() : pos - 1]
        table = ParsedTable(name=create.group(1).lower(), order_index=len(tables))
        for part in _split_top_level(body):
            upper = part.strip().upper()
            if not part.strip():
                continue
            if any(upper.startswith(prefix) for prefix in _SKIP_PREFIXES):
                continue
            table.columns.append(_parse_column(part, line_no))
        if not table.columns:
            raise DdlParseError(f"таблица {table.name!r} не содержит колонок", line_no)
        tables.append(table)
    if not tables:
        raise DdlParseError("DDL-скрипт не содержит операторов CREATE TABLE")
    return tables
