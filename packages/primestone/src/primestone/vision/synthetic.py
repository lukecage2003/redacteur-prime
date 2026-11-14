"""Planches synthétiques à vérité connue, pour les tests et le banc d'essai du détecteur.

Aucune œuvre protégée : mises en page aléatoires (grilles irrégulières, gouttières variables,
fonds clairs ou sombres, cases bordées ou en aplat, bruit graphique, texte dans les cases et
dans les gouttières). Le générateur est déterministe pour une graine donnée.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from PIL import Image, ImageDraw

from primestone.provenance import BoundingBox
from primestone.vision.models import ReadingDirection


@dataclass(frozen=True)
class SyntheticPage:
    image: Image.Image
    panels: list[BoundingBox]  # dans l'ordre de lecture
    direction: ReadingDirection
    description: str


def _split(total: int, parts: int, gutter: int, rng: random.Random) -> list[tuple[int, int]]:
    usable = total - gutter * (parts - 1)
    weights = [rng.uniform(0.6, 1.4) for _ in range(parts)]
    sizes = [int(usable * w / sum(weights)) for w in weights]
    out, pos = [], 0
    for size in sizes:
        out.append((pos, pos + size))
        pos += size + gutter
    return out


def generate_page(
    seed: int,
    *,
    size: tuple[int, int] = (1325, 2050),
    direction: ReadingDirection = ReadingDirection.LTR,
    gutter_crossing: bool = False,
) -> SyntheticPage:
    """`gutter_crossing` ajoute une bulle qui chevauche une gouttière entre deux rangées
    (cas réel fréquent et difficile pour un découpage par gouttières)."""
    rng = random.Random(seed)  # noqa: S311 - données de test, pas de cryptographie
    width, height = size
    dark = rng.random() < 0.2
    background = (12, 12, 16) if dark else (rng.randint(235, 255),) * 3
    ink = (240, 240, 240) if dark else (15, 15, 15)
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)

    margin = int(width * rng.uniform(0.03, 0.07))
    gutter = int(width * rng.uniform(0.012, 0.03))
    rows = rng.choice([1, 2, 3, 3, 4, 4, 5])
    row_spans = _split(height - 2 * margin, rows, gutter, rng)
    panels: list[BoundingBox] = []
    layout = []
    for top, bottom in row_spans:
        cols = rng.choice([1, 1, 2, 2, 3])
        col_spans = _split(width - 2 * margin, cols, gutter, rng)
        if direction is ReadingDirection.RTL:
            col_spans = list(reversed(col_spans))
        layout.append(cols)
        for left, right in col_spans:
            x0, y0 = margin + left, margin + top
            x1, y1 = margin + right, margin + bottom
            filled = rng.random() < 0.3
            if filled:
                tone = tuple(rng.randint(60, 200) for _ in range(3))
                draw.rectangle((x0, y0, x1, y1), fill=tone)
            else:
                draw.rectangle((x0, y0, x1, y1), outline=ink, width=rng.randint(2, 6))
            for _ in range(rng.randint(1, 6)):  # « dessin » contenu dans la case
                r = rng.randint(5, max(6, min(x1 - x0, y1 - y0) // 6))
                cx = rng.randint(x0 + r + 8, max(x0 + r + 9, x1 - r - 8))
                cy = rng.randint(y0 + r + 8, max(y0 + r + 9, y1 - r - 8))
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ink, width=3)
            draw.text((x0 + 15, y0 + 15), f"P{len(panels) + 1}", fill=ink)
            panels.append(
                BoundingBox(
                    x=x0 / width,
                    y=y0 / height,
                    width=(x1 - x0 + 1) / width,
                    height=(y1 - y0 + 1) / height,
                )
            )
    if gutter_crossing and len(row_spans) > 1:
        boundary = margin + row_spans[0][1] + gutter // 2
        cx = rng.randint(width // 4, 3 * width // 4)
        rx, ry = width // 10, gutter * 3
        draw.ellipse(
            (cx - rx, boundary - ry, cx + rx, boundary + ry), fill=background, outline=ink, width=3
        )
    # Numéro de page dans la marge basse : ne doit pas devenir une case.
    draw.text((width // 2, height - margin // 2), str(seed % 40 + 1), fill=ink)
    return SyntheticPage(
        image=image,
        panels=panels,
        direction=direction,
        description=(
            f"{rows} rangée(s) {layout}, gouttière {gutter}px, "
            f"fond {'sombre' if dark else 'clair'}{', bulle à cheval' if gutter_crossing else ''}"
        ),
    )
