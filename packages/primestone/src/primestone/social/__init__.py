"""Social Intelligence (phase 9) : déclinaisons par plateforme d'un livrable approuvé,
construites à partir des faits vérifiés — coût nul."""

from primestone.social.platforms import CHECKED_ON, PLATFORMS, PlatformSpec
from primestone.social.strategy import METHOD, Beat, beats, build_package, render

__all__ = [
    "CHECKED_ON",
    "METHOD",
    "PLATFORMS",
    "Beat",
    "PlatformSpec",
    "beats",
    "build_package",
    "render",
]
