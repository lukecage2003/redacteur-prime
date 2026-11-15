"""Citations de cases : chacune doit avoir un enregistrement de droits avant la production.

Le registre ne juge pas la légalité (droit de courte citation limité) : il trace la source,
la base juridique invoquée, la preuve et les limites, pour décision humaine.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Connection, text

from primestone.forensic import fold

# Même forme que le Fact Checker : « [Titre, p. 12, case 3] » ; copiée pour éviter un cycle
# d'import (editorial → storytelling → …).
_CITATION = re.compile(
    r"\[(?:(?P<doc>[^\[\]]+?),\s*)?p\.\s*(?P<page>\d+)(?:,\s*case\s*(?P<panel>\d+))?\]",
    re.IGNORECASE,
)


def panel_citations(script: str) -> list[dict[str, Any]]:
    """Citations qui désignent une case précise (donc une image montrée en production)."""
    found: dict[tuple[str, int, int], dict[str, Any]] = {}
    for m in _CITATION.finditer(script):
        if m.group("panel") is None:
            continue
        key = (fold(m.group("doc") or ""), int(m.group("page")), int(m.group("panel")))
        found.setdefault(
            key,
            {
                "document": (m.group("doc") or "").strip() or None,
                "page": key[1],
                "panel": key[2],
                "citation": m.group(0),
            },
        )
    return list(found.values())


def missing_rights(conn: Connection, script_id: Any) -> list[dict[str, Any]]:
    """Citations de cases du script (dernière version) sans droit actif et non échu."""
    content = conn.execute(
        text(
            "SELECT content FROM script_version WHERE script_id = :s ORDER BY number DESC LIMIT 1"
        ),
        {"s": script_id},
    ).scalar_one_or_none()
    citations = panel_citations(content or "")
    if not citations:
        return []
    records = (
        conn.execute(
            text(
                "SELECT script_id, document_title, page_number, panel_number FROM rights_record "
                "WHERE kind = 'PANEL_QUOTE' AND status = 'ACTIVE' "
                "AND (expires_on IS NULL OR expires_on >= current_date) "
                "AND (script_id IS NULL OR script_id = :s)"
            ),
            {"s": script_id},
        )
        .mappings()
        .all()
    )
    missing = []
    for c in citations:
        covered = any(
            r["page_number"] == c["page"]
            and r["panel_number"] == c["panel"]
            and (
                (c["document"] and fold(r["document_title"] or "") == fold(c["document"]))
                or (not c["document"] and r["script_id"] == script_id)
            )
            for r in records
        )
        if not covered:
            missing.append(c)
    return missing
