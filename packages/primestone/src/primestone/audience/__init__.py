"""Audience Intelligence (phase 15) : segments prouvés, graphe d'audience, communauté — coût
nul, sans données personnelles."""

from primestone.audience.community import METHOD, YouTubeComments, classify, insights
from primestone.audience.service import AudienceError, AudienceService

__all__ = ["METHOD", "AudienceError", "AudienceService", "YouTubeComments", "classify", "insights"]
