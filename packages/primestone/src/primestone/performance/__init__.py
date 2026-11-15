"""Performance Intelligence (phase 11) : métriques de la chaîne Primestone (export Studio
gratuit ou API Analytics OAuth), boucle d'apprentissage prudente — coût nul."""

from primestone.performance.importers import AnalyticsClient, ImportError_, parse_studio_csv
from primestone.performance.learning import METHOD, learn, spearman
from primestone.performance.service import PerformanceError, PerformanceService

__all__ = [
    "METHOD",
    "AnalyticsClient",
    "ImportError_",
    "PerformanceError",
    "PerformanceService",
    "learn",
    "parse_studio_csv",
    "spearman",
]
