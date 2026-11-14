"""Formats des plateformes : faits datés et sourcés, à revérifier avant publication.

Les plateformes changent souvent leurs règles : chaque format porte sa date de vérification et
sa source (documentation ou annonce officielle, désignée par son nom : à rouvrir et confirmer
avant publication, le réseau de développement n'y ayant pas accès). Les durées « cible » sont
des CHOIX ÉDITORIAUX, distingués des limites techniques.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CHECKED_ON = "2026-11-14"


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    name: str
    role: str
    aspect: str
    platform_limits: tuple[str, ...]
    editorial_target: str
    sources: tuple[str, ...]
    checked_on: str = CHECKED_ON

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "status": "à revérifier avant publication"}


PLATFORMS: dict[str, PlatformSpec] = {
    spec.key: spec
    for spec in (
        PlatformSpec(
            "youtube_long",
            "YouTube (vidéo longue)",
            "approfondissement : le dossier complet, en chapitres",
            "16:9",
            (
                "chapitres : le premier commence à 0:00, au moins 3 chapitres, "
                "chacun d'au moins 10 secondes",
            ),
            "un chapitre par section du dossier source",
            ("Aide YouTube : « Ajouter des chapitres à vos vidéos »",),
        ),
        PlatformSpec(
            "tiktok",
            "TikTok",
            "découverte : un fait fort, compréhensible sans contexte",
            "9:16",
            ("vidéos jusqu'à 60 minutes à l'import, 10 minutes enregistrées dans l'application",),
            "30 à 60 secondes (choix éditorial), une seule idée",
            ("Centre d'aide TikTok : création et import de vidéos",),
        ),
        PlatformSpec(
            "instagram_reels",
            "Instagram Reels",
            "découverte : un autre angle que TikTok, pas une copie",
            "9:16",
            ("Reels jusqu'à 3 minutes",),
            "30 à 60 secondes (choix éditorial)",
            ("Annonce Instagram de janvier 2025 : Reels jusqu'à 3 minutes",),
        ),
        PlatformSpec(
            "instagram_carousel",
            "Instagram (carrousel)",
            "mémorisation : un fait sourcé par carte, à sauvegarder",
            "4:5 (1080 x 1350 recommandé)",
            ("jusqu'à 20 photos ou vidéos par publication",),
            "couverture + 1 fait par carte + carte des sources",
            ("Annonce Instagram d'août 2024 : carrousels jusqu'à 20 éléments",),
        ),
    )
}
