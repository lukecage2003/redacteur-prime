"""Détection des cases et ordre de lecture par découpage récursif (« XY-cut »).

Principe : on repère l'encre (pixels qui diffèrent nettement du fond), puis on coupe
récursivement la page le long des gouttières — bandes horizontales d'abord, colonnes
ensuite. L'ordre de la récursion donne l'ordre de lecture (gauche→droite pour les comics,
droite→gauche pour le manga).

Gratuit, local, déterministe. Limites connues : cases qui se chevauchent, cases sans
gouttière (art « à fond perdu » qui traverse), gouttières non rectilignes. Ces cas sont
renvoyés comme une seule case englobante — jamais ignorés — et seront traités par
l'analyse visuelle (phase 3, fournisseur IA) puis mesurés par le banc d'essai.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from primestone.provenance import BoundingBox
from primestone.vision.models import Panel, ReadingDirection

SKEW_MIN_GAIN = 1.003  # mesuré : gain 1,000 sur page droite, >= 1,005 dès 0,3 degré
DETECTOR_VERSION = "xycut-2"  # 2 : redressement automatique des pages inclinées


@dataclass(frozen=True)
class PanelConfig:
    work_size: int = 1000  # plus grand côté de l'image de travail
    ink_threshold: int = 25  # écart minimal au fond pour être de l'« encre »
    gutter_ink_ratio: float = 0.004  # tolérance d'encre dans une gouttière
    min_gutter_ratio: float = 0.003  # largeur minimale d'une gouttière (fraction de page)
    min_panel_area_ratio: float = 0.012  # en dessous : bruit, numéro de page…
    max_depth: int = 8
    max_skew_degrees: float = 2.0  # redressement des scans inclinés (0 : désactivé)


def _background_level(gray: NDArray[np.int16]) -> int:
    height, width = gray.shape
    band = max(1, min(height, width) // 100)
    border = np.concatenate(
        [
            gray[:band, :].ravel(),
            gray[-band:, :].ravel(),
            gray[:, :band].ravel(),
            gray[:, -band:].ravel(),
        ]
    )
    return int(np.median(border))


def _runs(empty: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """Plages [début, fin) de valeurs vraies consécutives."""
    padded = np.concatenate([[False], empty, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2], strict=True)]


def _segments(profile: NDArray[np.int64], tolerance: int, min_gap: int) -> list[tuple[int, int]]:
    """Découpe un profil d'encre en segments séparés par des gouttières assez larges."""
    empty = profile <= tolerance
    gutters = [(a, b) for a, b in _runs(empty) if b - a >= min_gap and a > 0 and b < len(profile)]
    if not gutters:
        return []
    bounds = [0] + [x for gutter in gutters for x in gutter] + [len(profile)]
    return [(bounds[i], bounds[i + 1]) for i in range(0, len(bounds), 2)]


def _alignment(mask: Image.Image, angle: float) -> float:
    rotated = np.asarray(mask.rotate(angle, resample=Image.Resampling.NEAREST), dtype=bool)
    return float(rotated.sum(axis=1).var() + rotated.sum(axis=0).var())


def estimate_skew(ink: NDArray[np.bool_], max_degrees: float) -> float:
    """Angle (degrés) qui aligne le mieux gouttières et bords de cases sur les axes."""
    if max_degrees <= 0:
        return 0.0
    mask = Image.fromarray((ink * 255).astype(np.uint8))
    scale = 500 / max(mask.size)
    if scale < 1:
        mask = mask.resize((round(mask.width * scale), round(mask.height * scale)))
    best = 0.0
    for step, span in ((0.5, max_degrees), (0.1, 0.5), (0.025, 0.1)):
        candidates = np.arange(best - span, best + span + 1e-9, step)
        best = float(max(candidates, key=lambda a: _alignment(mask, float(a))))
    # On ne redresse que si le gain d'alignement est net : une page droite reste intacte.
    if abs(best) < 0.05 or _alignment(mask, best) < SKEW_MIN_GAIN * _alignment(mask, 0.0):
        return 0.0
    return best


def _unrotate(
    box: tuple[int, int, int, int], angle: float, width: int, height: int
) -> tuple[float, float, float, float]:
    """Boîte englobante, dans la page d'origine, d'une boîte de la page redressée."""
    x0, y0, x1, y1 = box
    cx, cy = width / 2, height / 2
    theta = np.deg2rad(angle)  # PIL tourne dans le sens antihoraire : on applique l'inverse
    cos, sin = np.cos(theta), np.sin(theta)
    xs, ys = [], []
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        dx, dy = x - cx, y - cy
        xs.append(cx + dx * cos + dy * sin)
        ys.append(cy - dx * sin + dy * cos)
    return (
        max(0.0, min(xs)),
        max(0.0, min(ys)),
        min(float(width), max(xs)),
        min(float(height), max(ys)),
    )


def detect_panels(
    image: Image.Image,
    *,
    direction: ReadingDirection = ReadingDirection.LTR,
    config: PanelConfig | None = None,
) -> list[Panel]:
    cfg = config or PanelConfig()
    work = image.convert("L")
    scale = cfg.work_size / max(work.size)
    if scale < 1:
        work = work.resize(
            (max(1, round(work.width * scale)), max(1, round(work.height * scale))),
            Image.Resampling.BILINEAR,
        )
    gray = np.asarray(work, dtype=np.int16)
    height, width = gray.shape
    background = _background_level(gray)
    ink = np.abs(gray - background) > cfg.ink_threshold
    angle = estimate_skew(ink, cfg.max_skew_degrees)
    if angle:
        straightened = work.rotate(
            angle, resample=Image.Resampling.BILINEAR, fillcolor=int(background)
        )
        ink = np.abs(np.asarray(straightened, dtype=np.int16) - background) > cfg.ink_threshold
    min_gap_y = max(2, round(cfg.min_gutter_ratio * height))
    min_gap_x = max(2, round(cfg.min_gutter_ratio * width))
    boxes: list[tuple[int, int, int, int]] = []

    def visit(y0: int, y1: int, x0: int, x1: int, depth: int) -> None:
        region = ink[y0:y1, x0:x1]
        rows = np.flatnonzero(region.any(axis=1))
        cols = np.flatnonzero(region.any(axis=0))
        if rows.size == 0 or cols.size == 0:
            return
        y0, y1 = y0 + int(rows[0]), y0 + int(rows[-1]) + 1  # rognage des marges vides
        x0, x1 = x0 + int(cols[0]), x0 + int(cols[-1]) + 1
        region = ink[y0:y1, x0:x1]
        if depth < cfg.max_depth:
            row_profile = region.sum(axis=1)
            bands = _segments(row_profile, int(cfg.gutter_ink_ratio * (x1 - x0)), min_gap_y)
            if bands:
                for a, b in bands:
                    visit(y0 + a, y0 + b, x0, x1, depth + 1)
                return
            col_profile = region.sum(axis=0)
            columns = _segments(col_profile, int(cfg.gutter_ink_ratio * (y1 - y0)), min_gap_x)
            if columns:
                if direction is ReadingDirection.RTL:
                    columns = list(reversed(columns))
                for a, b in columns:
                    visit(y0, y1, x0 + a, x0 + b, depth + 1)
                return
        boxes.append((x0, y0, x1, y1))

    visit(0, height, 0, width, 0)
    min_area = cfg.min_panel_area_ratio * width * height
    kept = [b for b in boxes if (b[2] - b[0]) * (b[3] - b[1]) >= min_area]
    final = [
        _unrotate(b, angle, width, height) if angle else tuple(float(v) for v in b) for b in kept
    ]
    return [
        Panel(
            index=i,
            bbox=BoundingBox(
                x=x0 / width,
                y=y0 / height,
                width=(x1 - x0) / width,
                height=(y1 - y0) / height,
            ),
        )
        for i, (x0, y0, x1, y1) in enumerate(final, start=1)
    ]
