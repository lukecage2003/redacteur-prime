"""Performance Intelligence (phase 11) : métriques de la chaîne Primestone (export Studio
gratuit ou API Analytics OAuth), boucle d'apprentissage prudente — coût nul."""

from primestone.performance.experiments import decide, wilson
from primestone.performance.importers import AnalyticsClient, ImportError_, parse_studio_csv
from primestone.performance.learning import METHOD, learn, spearman
from primestone.performance.measurement import OBJECTIVE_KPIS, evaluate
from primestone.performance.oauth import OAuthError, access_token_provider, consent_url
from primestone.performance.service import PerformanceError, PerformanceService

__all__ = [
    "METHOD",
    "OBJECTIVE_KPIS",
    "AnalyticsClient",
    "ImportError_",
    "OAuthError",
    "PerformanceError",
    "PerformanceService",
    "access_token_provider",
    "consent_url",
    "decide",
    "evaluate",
    "learn",
    "parse_studio_csv",
    "spearman",
    "wilson",
]
