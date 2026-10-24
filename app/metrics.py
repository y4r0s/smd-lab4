"""Метрики Prometheus (ЛР № 4, промпты 4.3 и 4.3.1): бизнес-метрики СМД и HTTP-метрики.

Бизнес-метрики (4): количество проектов, количество сравнений, время сравнения схем,
время экспорта миграции. HTTP-метрики добавлены при верификации для панели Grafana
(активность, время отклика, ошибки).
"""
from prometheus_client import Counter, Histogram

# количество созданных проектов сравнения
PROJECTS_TOTAL = Counter("smd_projects", "Количество созданных проектов сравнения")

# количество созданных сравнений схем
COMPARISONS_TOTAL = Counter("smd_comparisons", "Количество созданных сравнений схем")

# время сравнения схем (разбор DDL + поиск различий)
COMPARISON_DURATION = Histogram(
    "smd_comparison_duration_seconds",
    "Время выполнения сравнения схем",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# время экспорта SQL-скрипта миграции
EXPORT_DURATION = Histogram(
    "smd_export_duration_seconds",
    "Время экспорта SQL-скрипта миграции",
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

# HTTP-запросы к API (без служебных маршрутов /metrics и /api/health)
HTTP_REQUESTS = Counter(
    "smd_http_requests",
    "HTTP-запросы к API",
    ["method", "endpoint", "status"],
)

# длительность обработки HTTP-запроса
HTTP_REQUEST_DURATION = Histogram(
    "smd_http_request_duration_seconds",
    "Длительность обработки HTTP-запроса",
    ["method", "endpoint"],
)
