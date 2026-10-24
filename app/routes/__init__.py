"""Маршруты REST API: 12 конечных точек (CRUD проектов, сравнения, миграции, health)."""
from . import comparisons, migrations, projects

__all__ = ["comparisons", "migrations", "projects"]
