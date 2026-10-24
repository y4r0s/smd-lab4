"""DiffEngine — движок сравнения схем (сервисный класс ЛР № 2).

Шаблон «Стратегия» (ЛР № 2, таблица 8): интерфейс IComparisonStrategy
и две реализации — TableOnlyDiffStrategy и ColumnAwareDiffStrategy.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .ddl_parser import ParsedTable


@dataclass
class DiffItem:
    """Различие, выявленное движком сравнения (до сохранения в БД)."""

    object_type: str  # table | column
    object_name: str
    path: str
    diff_type: str  # ADDED | REMOVED | MODIFIED
    details: dict = field(default_factory=dict)


class IComparisonStrategy(ABC):
    """Контракт алгоритма сравнения схем (шаблон «Стратегия», ЛР № 2)."""

    @abstractmethod
    def compare(self, source: list[ParsedTable], target: list[ParsedTable]) -> list[DiffItem]:
        """Сравнить список таблиц source со списком target."""


def _index_by_name(tables: list[ParsedTable]) -> dict[str, ParsedTable]:
    return {t.name: t for t in tables}


class TableOnlyDiffStrategy(IComparisonStrategy):
    """Сравнение на уровне таблиц: появление и удаление таблиц (Т1)."""

    def compare(self, source: list[ParsedTable], target: list[ParsedTable]) -> list[DiffItem]:
        src = _index_by_name(source)
        tgt = _index_by_name(target)
        diffs: list[DiffItem] = []
        for name in tgt:
            if name not in src:
                diffs.append(
                    DiffItem(
                        object_type="table",
                        object_name=name,
                        path=name,
                        diff_type="ADDED",
                        details={"columns": [c.to_dict() for c in tgt[name].columns]},
                    )
                )
        for name in src:
            if name not in tgt:
                diffs.append(
                    DiffItem(object_type="table", object_name=name, path=name, diff_type="REMOVED")
                )
        return diffs


class ColumnAwareDiffStrategy(IComparisonStrategy):
    """Сравнение с учётом колонок: добавление, удаление и изменение колонок (Т1, Т2)."""

    def compare(self, source: list[ParsedTable], target: list[ParsedTable]) -> list[DiffItem]:
        diffs = TableOnlyDiffStrategy().compare(source, target)
        src = _index_by_name(source)
        tgt = _index_by_name(target)
        for name in src:
            if name not in tgt:
                continue
            src_cols = {c.name: c for c in src[name].columns}
            tgt_cols = {c.name: c for c in tgt[name].columns}
            for col_name, col in tgt_cols.items():
                if col_name not in src_cols:
                    diffs.append(
                        DiffItem(
                            object_type="column",
                            object_name=col_name,
                            path=f"{name}.{col_name}",
                            diff_type="ADDED",
                            details=col.to_dict(),
                        )
                    )
                else:
                    old = src_cols[col_name]
                    if (
                        old.data_type != col.data_type
                        or old.nullable != col.nullable
                        or old.is_pk != col.is_pk
                    ):
                        diffs.append(
                            DiffItem(
                                object_type="column",
                                object_name=col_name,
                                path=f"{name}.{col_name}",
                                diff_type="MODIFIED",
                                details={"before": old.to_dict(), "after": col.to_dict()},
                            )
                        )
            for col_name in src_cols:
                if col_name not in tgt_cols:
                    diffs.append(
                        DiffItem(
                            object_type="column",
                            object_name=col_name,
                            path=f"{name}.{col_name}",
                            diff_type="REMOVED",
                            details=src_cols[col_name].to_dict(),
                        )
                    )
        return diffs


STRATEGIES: dict[str, IComparisonStrategy] = {
    "table": TableOnlyDiffStrategy(),
    "column": ColumnAwareDiffStrategy(),
}


def get_strategy(name: str) -> IComparisonStrategy:
    """Выбрать стратегию сравнения по имени (таблица | колонка)."""
    if name not in STRATEGIES:
        raise KeyError(f"неизвестная стратегия сравнения: {name!r}")
    return STRATEGIES[name]
