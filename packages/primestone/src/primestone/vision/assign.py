"""Rattachement des zones de texte aux cases et ordre de lecture du texte."""

from __future__ import annotations

from primestone.provenance import BoundingBox
from primestone.vision.models import Panel, ReadingDirection, TextRegion

MIN_OVERLAP = 0.5  # part de la zone de texte qui doit se trouver dans la case


def intersection_area(a: BoundingBox, b: BoundingBox) -> float:
    w = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
    h = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    return max(0.0, w) * max(0.0, h)


def iou(a: BoundingBox, b: BoundingBox) -> float:
    inter = intersection_area(a, b)
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0 else 0.0


def assign_texts(
    panels: list[Panel],
    texts: list[TextRegion],
    direction: ReadingDirection = ReadingDirection.LTR,
) -> list[TextRegion]:
    """Attribue chaque texte à la case qui le contient le plus (≥ 50 % de sa surface),
    puis numérote les textes dans l'ordre de lecture : ordre des cases, puis haut→bas et
    gauche→droite (droite→gauche en RTL) à l'intérieur d'une case. Les textes hors case
    sont placés après la case la plus proche qui les précède verticalement."""
    placed: list[tuple[tuple[float, float, float], TextRegion]] = []
    for text in texts:
        area = text.bbox.width * text.bbox.height
        best: Panel | None = None
        best_ratio = 0.0
        for panel in panels:
            ratio = intersection_area(text.bbox, panel.bbox) / area if area else 0.0
            if ratio > best_ratio:
                best, best_ratio = panel, ratio
        panel_index = best.index if best is not None and best_ratio >= MIN_OVERLAP else None
        cx = text.bbox.x + text.bbox.width / 2
        horizontal = cx if direction is ReadingDirection.LTR else -cx
        if panel_index is not None:
            rank = float(panel_index)
        else:
            above = [p.index for p in panels if p.bbox.y <= text.bbox.y]
            rank = (max(above) if above else 0) + 0.5
        placed.append(
            (
                (rank, round(text.bbox.y, 2), horizontal),
                text.model_copy(update={"panel_index": panel_index}),
            )
        )
    placed.sort(key=lambda item: item[0])
    return [t.model_copy(update={"order": i}) for i, (_, t) in enumerate(placed, start=1)]
