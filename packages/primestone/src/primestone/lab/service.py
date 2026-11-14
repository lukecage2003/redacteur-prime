"""Research et Theory Laboratory : théories structurées, preuves vérifiées, journal.

Une théorie n'est jamais CANON. Chaque preuve pointe vers une page exacte ; si elle cite un
extrait et que la page est transcrite, l'extrait DOIT y figurer (sinon elle est refusée). Rien
n'est effacé : une preuve est retirée avec un motif, et chaque action est journalisée.
Le Theory Researcher propose des passages candidats ; seul un humain les classe pour ou contre.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.forensic import ForensicService, TextRow, fold
from primestone.knowledge import KnowledgeService, hybrid_search
from primestone.lab.scoring import METHOD, EvidenceInput, Score, score

ROLES = ("SUPPORTS", "REFUTES")
EVIDENCE_LEVELS = ("CANON", "INTERPRETATION", "SPECULATION")


class LabError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _found(rows: Sequence[TextRow], page: int, panel: int | None, excerpt: str) -> bool | None:
    """True/False si la page est transcrite, None sinon (invérifiable)."""
    on_page = [r for r in rows if r.page == page]
    if not on_page:
        return None
    scoped = [r for r in on_page if panel is None or r.panel_index == panel]
    return fold(excerpt) in " ".join(fold(r.text) for r in scoped)


class TheoryLab:
    def __init__(
        self, engine: Engine, forensic: ForensicService, knowledge: KnowledgeService
    ) -> None:
        self._engine = engine
        self._forensic = forensic
        self._knowledge = knowledge

    # --- Journal et calcul ---------------------------------------------------------------------

    @staticmethod
    def _log(
        conn: Connection,
        theory_id: UUID,
        action: str,
        author: str,
        detail: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        conn.execute(
            text(
                "INSERT INTO theory_event (theory_id, action, detail, author, reason) "
                "VALUES (:t, :a, CAST(:d AS jsonb), :author, :r)"
            ),
            {"t": theory_id, "a": action, "d": _json(detail or {}), "author": author, "r": reason},
        )

    @staticmethod
    def _score(conn: Connection, theory_id: UUID) -> Score:
        searched = conn.execute(
            text("SELECT counter_search_at IS NOT NULL FROM theory WHERE id = :t"),
            {"t": theory_id},
        ).scalar_one()
        evidence = [
            EvidenceInput(r[0], r[1], r[2], r[3])
            for r in conn.execute(
                text(
                    "SELECT role, level, verified, excerpt IS NOT NULL FROM theory_evidence "
                    "WHERE theory_id = :t AND retracted_at IS NULL"
                ),
                {"t": theory_id},
            ).all()
        ]
        return score(evidence, counter_search_done=bool(searched))

    def _recompute(self, conn: Connection, theory_id: UUID) -> dict[str, Any]:
        result = self._score(conn, theory_id)
        conn.execute(
            text(
                "UPDATE theory SET level = :l, status = :s, confidence = :c, updated_at = now() "
                "WHERE id = :t"
            ),
            {"l": result.level, "s": result.status, "c": result.confidence, "t": theory_id},
        )
        return {"level": result.level, "status": result.status, "confidence": result.confidence}

    def _theory_row(self, conn: Connection, theory_id: UUID, *, lock: bool = False) -> Any:
        query = "SELECT id, document_ids, subjects, claim FROM theory WHERE id = :t"
        row = conn.execute(
            text(query + " FOR UPDATE" if lock else query), {"t": theory_id}
        ).one_or_none()
        if row is None:
            raise LookupError("théorie introuvable")
        return row

    # --- Création et preuves -----------------------------------------------------------------

    def create(
        self,
        *,
        title: str,
        claim: str,
        document_ids: Sequence[UUID],
        subjects: Sequence[str] = (),
        author: str,
    ) -> UUID:
        if not title.strip() or not claim.strip():
            raise LabError("titre et énoncé obligatoires")
        if not author.strip():
            raise LabError("auteur obligatoire")
        if not document_ids:
            raise LabError("au moins un document est requis")
        with self._engine.begin() as conn:
            known = conn.execute(
                text("SELECT count(*) FROM document WHERE id = ANY(:ids)"),
                {"ids": list(document_ids)},
            ).scalar_one()
            if known != len(set(document_ids)):
                raise LabError("document inconnu")
            theory_id: UUID = conn.execute(
                text(
                    "INSERT INTO theory (title, claim, document_ids, subjects, author) "
                    "VALUES (:title, :claim, CAST(:docs AS jsonb), CAST(:subj AS jsonb), :a) "
                    "RETURNING id"
                ),
                {
                    "title": title.strip(),
                    "claim": claim.strip(),
                    "docs": _json([str(d) for d in dict.fromkeys(document_ids)]),
                    "subj": _json([s.strip() for s in subjects if s.strip()]),
                    "a": author,
                },
            ).scalar_one()
            self._log(conn, theory_id, "CREATED", author, {"claim": claim.strip()})
            self._recompute(conn, theory_id)
        return theory_id

    def add_evidence(
        self,
        theory_id: UUID,
        *,
        role: str,
        document_id: UUID,
        page: int,
        panel: int | None = None,
        excerpt: str | None = None,
        level: str = "CANON",
        note: str | None = None,
        author: str,
        origin: str = "HUMAN",
    ) -> dict[str, Any]:
        if role not in ROLES:
            raise LabError(f"rôle inconnu : {role} (SUPPORTS ou REFUTES)")
        if level not in EVIDENCE_LEVELS:
            raise LabError(f"niveau inconnu : {level}")
        if origin not in ("HUMAN", "RESEARCHER"):
            raise LabError(f"origine inconnue : {origin}")
        if not author.strip():
            raise LabError("auteur obligatoire")
        excerpt = excerpt.strip() if excerpt and excerpt.strip() else None
        if level != "CANON" and not (note and note.strip()):
            raise LabError("une preuve INTERPRETATION ou SPECULATION exige une note explicative")
        with self._engine.begin() as conn:
            theory = self._theory_row(conn, theory_id, lock=True)
            if str(document_id) not in theory.document_ids:
                raise LabError("document hors du périmètre de la théorie")
            page_count = conn.execute(
                text("SELECT page_count FROM document WHERE id = :d"), {"d": document_id}
            ).scalar_one_or_none()
            if not page_count or not 1 <= page <= page_count:
                raise LabError(f"page {page} inexistante")
            verified = False
            if excerpt:
                found = _found(self._forensic.text_rows([document_id]), page, panel, excerpt)
                if found is False:
                    where = f"p. {page}" + (f", case {panel}" if panel else "")
                    raise LabError(f"extrait « {excerpt} » absent de la transcription ({where})")
                verified = bool(found)
            evidence_id: UUID = conn.execute(
                text(
                    """
                    INSERT INTO theory_evidence (theory_id, role, document_id, page_number,
                           panel_index, excerpt, verified, level, note, origin, added_by)
                    VALUES (:t, :role, :d, :p, :panel, :x, :v, :l, :n, :o, :a) RETURNING id
                    """
                ),
                {
                    "t": theory_id,
                    "role": role,
                    "d": document_id,
                    "p": page,
                    "panel": panel,
                    "x": excerpt,
                    "v": verified,
                    "l": level,
                    "n": note,
                    "o": origin,
                    "a": author,
                },
            ).scalar_one()
            after = self._recompute(conn, theory_id)
            self._log(
                conn,
                theory_id,
                "EVIDENCE_ADDED",
                author,
                {"evidence_id": str(evidence_id), "role": role, "verified": verified, **after},
            )
        return {"id": str(evidence_id), "verified": verified, **after}

    def retract_evidence(self, evidence_id: UUID, *, author: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise LabError("un motif est obligatoire")
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT theory_id, retracted_at FROM theory_evidence WHERE id = :e FOR UPDATE"
                ),
                {"e": evidence_id},
            ).one_or_none()
            if row is None:
                raise LookupError("preuve introuvable")
            if row.retracted_at is not None:
                raise LabError("preuve déjà retirée")
            conn.execute(
                text(
                    "UPDATE theory_evidence SET retracted_at = now(), retraction_reason = :r "
                    "WHERE id = :e"
                ),
                {"r": reason, "e": evidence_id},
            )
            after = self._recompute(conn, row.theory_id)
            self._log(
                conn,
                row.theory_id,
                "EVIDENCE_RETRACTED",
                author,
                {"evidence_id": str(evidence_id), **after},
                reason,
            )
        return after

    def add_alternative(self, theory_id: UUID, *, text_: str, author: str) -> UUID:
        if not text_.strip() or not author.strip():
            raise LabError("texte et auteur obligatoires")
        with self._engine.begin() as conn:
            self._theory_row(conn, theory_id)
            alt_id: UUID = conn.execute(
                text(
                    "INSERT INTO theory_alternative (theory_id, text, author) "
                    "VALUES (:t, :x, :a) RETURNING id"
                ),
                {"t": theory_id, "x": text_.strip(), "a": author},
            ).scalar_one()
            self._log(conn, theory_id, "ALTERNATIVE_ADDED", author, {"text": text_.strip()})
        return alt_id

    # --- Theory Researcher (gratuit) ---------------------------------------------------------

    def search(
        self, query: str, document_ids: Sequence[UUID], *, limit: int = 10
    ) -> dict[str, Any]:
        """Passages et observations pertinents pour une question (aucun jugement)."""
        hits = hybrid_search(
            self._engine, self._knowledge.embedder, query, document_ids=document_ids, limit=limit
        )
        passages = [h for h in hits if h["kind"] == "TEXT"]
        terms = {t for t in fold(query).split() if len(t) > 3}
        observations = [
            o
            for o in self._forensic.observations(document_ids, limit=10_000)
            if o["kind"] in ("CLAIM", "CONTRADICTION_CANDIDATE", "FIRST_APPEARANCE")
            and terms & set(fold(f"{o.get('subject') or ''} {o['statement']}").split())
        ][:limit]
        return {"query": query, "passages": passages, "observations": observations}

    def research(
        self, theory_id: UUID, *, author: str = "theory_researcher", limit: int = 10
    ) -> dict[str, Any]:
        """Cherche des candidats POUR et CONTRE ; marque la recherche de contre-preuves faite.

        Les contradictions candidates touchant les sujets sont proposées comme contre-preuves
        possibles ; les passages restent à classer par un humain (le moteur ne juge pas)."""
        with self._engine.connect() as conn:
            theory = self._theory_row(conn, theory_id)
            cited = {
                (str(r[0]), r[1], fold(r[2] or ""))
                for r in conn.execute(
                    text(
                        "SELECT document_id, page_number, excerpt FROM theory_evidence "
                        "WHERE theory_id = :t AND retracted_at IS NULL"
                    ),
                    {"t": theory_id},
                ).all()
            }
        documents = [UUID(d) for d in theory.document_ids]
        query = " ".join([theory.claim, *theory.subjects])
        found = self.search(query, documents, limit=limit)
        passages = [
            p
            for p in found["passages"]
            if (p["document_id"], p["page"], fold(p["content"])) not in cited
        ]
        subjects = {fold(s) for s in theory.subjects}
        contradictions = [
            o
            for o in self._forensic.observations(documents, kind="CONTRADICTION_CANDIDATE")
            if not subjects or fold(o.get("subject") or "") in subjects
        ]
        claims = [
            o
            for o in self._forensic.observations(documents, kind="CLAIM", limit=10_000)
            if fold(o.get("subject") or "") in subjects
        ]
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE theory SET counter_search_at = now() WHERE id = :t"),
                {"t": theory_id},
            )
            after = self._recompute(conn, theory_id)
            self._log(
                conn,
                theory_id,
                "COUNTER_SEARCH",
                author,
                {
                    "passages": len(passages),
                    "contradictions": len(contradictions),
                    "claims": len(claims),
                    **after,
                },
            )
        return {
            "passages": passages,
            "possible_counter_evidence": contradictions,
            "claims": claims,
            **after,
        }

    # --- Lecture -----------------------------------------------------------------------------

    def theories(
        self, *, status: str | None = None, level: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, title, claim, level, status, confidence, subjects, author,
                           counter_search_at, created_at, updated_at,
                           (SELECT count(*) FROM theory_evidence e WHERE e.theory_id = theory.id
                               AND e.retracted_at IS NULL AND e.role = 'SUPPORTS') AS supports,
                           (SELECT count(*) FROM theory_evidence e WHERE e.theory_id = theory.id
                               AND e.retracted_at IS NULL AND e.role = 'REFUTES') AS refutes
                      FROM theory
                     WHERE (CAST(:status AS text) IS NULL OR status = :status)
                       AND (CAST(:level AS text) IS NULL OR level = :level)
                     ORDER BY updated_at DESC LIMIT :limit
                    """
                ),
                {"status": status, "level": level, "limit": limit},
            ).mappings()
            return [{**dict(r), "id": str(r["id"])} for r in rows]

    def theory(self, theory_id: UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(text("SELECT * FROM theory WHERE id = :t"), {"t": theory_id})
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            evidence = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT e.*, c.title AS document_title FROM theory_evidence e "
                        "JOIN document d ON d.id = e.document_id "
                        "JOIN comic c ON c.id = d.comic_id "
                        "WHERE e.theory_id = :t ORDER BY e.created_at"
                    ),
                    {"t": theory_id},
                ).mappings()
            ]
            alternatives = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT id, text, author, created_at FROM theory_alternative "
                        "WHERE theory_id = :t ORDER BY created_at"
                    ),
                    {"t": theory_id},
                ).mappings()
            ]
            events = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT action, detail, author, reason, created_at FROM theory_event "
                        "WHERE theory_id = :t ORDER BY created_at, id"
                    ),
                    {"t": theory_id},
                ).mappings()
            ]
            current = self._score(conn, theory_id)
            titles = {
                str(r[0]): {"id": str(r[0]), "title": r[1], "page_count": r[2]}
                for r in conn.execute(
                    text(
                        "SELECT d.id, c.title, d.page_count FROM document d "
                        "JOIN comic c ON c.id = d.comic_id WHERE d.id = ANY(:ids)"
                    ),
                    {"ids": [UUID(d) for d in row["document_ids"]]},
                ).all()
            }
        # Revérification : une transcription corrigée depuis peut invalider un extrait.
        rows_by_doc: dict[UUID, list[TextRow]] = {}
        for e in evidence:
            e["id"] = str(e["id"])
            e["theory_id"] = str(e["theory_id"])
            doc = e["document_id"]
            e["document_id"] = str(doc)
            e["still_found"] = None
            if e["excerpt"]:
                if doc not in rows_by_doc:
                    rows_by_doc[doc] = self._forensic.text_rows([doc])
                e["still_found"] = _found(
                    rows_by_doc[doc], e["page_number"], e["panel_index"], e["excerpt"]
                )
        for a in alternatives:
            a["id"] = str(a["id"])
        return {
            **dict(row),
            "id": str(row["id"]),
            "documents": [titles[d] for d in row["document_ids"] if d in titles],
            "evidence": evidence,
            "alternatives": alternatives,
            "events": events,
            "scoring": {
                "method": METHOD,
                "support": current.support,
                "against": current.against,
                "explanation": list(current.explanation),
            },
        }
