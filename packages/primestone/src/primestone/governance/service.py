"""Gouvernance éditoriale : proposé → approuvé → appliqué, journalisé et réversible.

Règles imposées côté serveur :
- seul le rôle FOUNDER approuve, rejette ou annule ; un agent ne peut que proposer ;
- une action sans politique connue exige l'approbation (défaut prudent) ;
- un changement de politique exige toujours l'approbation, et POLICY_CHANGE ne peut jamais
  devenir automatique ;
- chaque application enregistre l'état antérieur, ce qui rend l'annulation exacte.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

FOUNDER = "FOUNDER"
DEFAULT_BRAND = "primestone"
ALWAYS_APPROVED = ("POLICY_CHANGE",)
_LOAD = "SELECT * FROM editorial_decision WHERE id = :id"
_LOAD_LOCKED = _LOAD + " FOR UPDATE"


class GovernanceError(ValueError):
    pass


# Un gestionnaire applique (forward=True) ou annule (forward=False) une décision ; il renvoie
# l'état antérieur à mémoriser (application) ou None (annulation).
Handler = Callable[[Connection, dict[str, Any], bool], dict[str, Any] | None]
_HANDLERS: dict[str, Handler] = {}


def register_handler(action: str, handler: Handler) -> None:
    _HANDLERS[action] = handler


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# --- Gestionnaires de la phase 20 ---------------------------------------------------------


def _charter(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    version = int(decision["proposal"]["charter_version"])
    if forward:
        previous = (
            conn.execute(
                text(
                    "SELECT version FROM brand_charter WHERE status = 'APPROVED' AND brand_id = :b "
                    "AND language IS NOT DISTINCT FROM (SELECT language FROM brand_charter "
                    "WHERE version = :v)"
                ),
                {"b": decision["brand_id"], "v": version},
            )
            .scalars()
            .all()
        )
        conn.execute(
            text("UPDATE brand_charter SET status = 'RETIRED' WHERE version = ANY(:p)"),
            {"p": list(previous)},
        )
        conn.execute(
            text(
                "UPDATE brand_charter SET status = 'APPROVED', approved_by = :by, "
                "approved_at = now() WHERE version = :v"
            ),
            {"by": decision["decided_by"], "v": version},
        )
        return {"retired_versions": list(previous)}
    restored = decision["proposal"].get("previous", {}).get("retired_versions", [])
    conn.execute(
        text("UPDATE brand_charter SET status = 'RETIRED' WHERE version = :v"), {"v": version}
    )
    conn.execute(
        text("UPDATE brand_charter SET status = 'APPROVED' WHERE version = ANY(:p)"),
        {"p": restored},
    )
    return None


def _pillar(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    op = decision["proposal"]["op"]
    target = {("create", True): "ACTIVE", ("create", False): "RETIRED"}.get((op, forward))
    if target is None:
        target = "RETIRED" if forward else "ACTIVE"
    conn.execute(
        text("UPDATE editorial_pillar SET status = :s, version = version + 1 WHERE id = :id"),
        {"s": target, "id": decision["subject_id"]},
    )
    return {"op": op} if forward else None


def _policy(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    proposal = decision["proposal"]
    if forward:
        current = (
            conn.execute(
                text(
                    "SELECT requires_approval, note FROM editorial_policy "
                    "WHERE brand_id = :b AND action = :a"
                ),
                {"b": decision["brand_id"], "a": proposal["action"]},
            )
            .mappings()
            .one_or_none()
        )
        conn.execute(
            text(
                "INSERT INTO editorial_policy (brand_id, action, requires_approval, note) "
                "VALUES (:b, :a, :r, :n) ON CONFLICT (brand_id, action) DO UPDATE SET "
                "requires_approval = :r, note = :n, version = editorial_policy.version + 1, "
                "updated_at = now()"
            ),
            {
                "b": decision["brand_id"],
                "a": proposal["action"],
                "r": proposal["requires_approval"],
                "n": proposal.get("note"),
            },
        )
        return dict(current) if current else {"requires_approval": None}
    before = proposal.get("previous") or {}
    if before.get("requires_approval") is None:
        conn.execute(
            text("DELETE FROM editorial_policy WHERE brand_id = :b AND action = :a"),
            {"b": decision["brand_id"], "a": proposal["action"]},
        )
    else:
        conn.execute(
            text(
                "UPDATE editorial_policy SET requires_approval = :r, note = :n, "
                "version = version + 1, updated_at = now() WHERE brand_id = :b AND action = :a"
            ),
            {
                "b": decision["brand_id"],
                "a": proposal["action"],
                "r": before["requires_approval"],
                "n": before.get("note"),
            },
        )
    return None


register_handler("CHARTER_CHANGE", _charter)
register_handler("PILLAR_CHANGE", _pillar)
register_handler("POLICY_CHANGE", _policy)


class GovernanceService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- Lecture ---------------------------------------------------------------------------

    def brand(self, slug: str = DEFAULT_BRAND) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(text("SELECT * FROM media_brand WHERE slug = :s"), {"s": slug})
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise GovernanceError(f"marque inconnue : {slug}")
        return dict(row)

    def brands(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(text("SELECT * FROM media_brand ORDER BY created_at"))
                .mappings()
                .all()
            ]

    def policies(self, slug: str = DEFAULT_BRAND) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT p.action, p.requires_approval, p.approver, p.note, p.version, "
                        "p.updated_at FROM editorial_policy p JOIN media_brand b "
                        "ON b.id = p.brand_id WHERE b.slug = :s ORDER BY p.action"
                    ),
                    {"s": slug},
                )
                .mappings()
                .all()
            ]

    def pillars(self, slug: str = DEFAULT_BRAND) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT p.id, p.name, p.description, p.rules, p.status, p.version "
                        "FROM editorial_pillar p JOIN media_brand b ON b.id = p.brand_id "
                        "WHERE b.slug = :s ORDER BY p.status, p.name"
                    ),
                    {"s": slug},
                )
                .mappings()
                .all()
            ]

    def decisions(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT * FROM editorial_decision "
                        "WHERE (CAST(:s AS text) IS NULL OR status = :s) "
                        "ORDER BY created_at DESC LIMIT :n"
                    ),
                    {"s": status, "n": limit},
                )
                .mappings()
                .all()
            ]

    def decision(self, decision_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            return self._load(conn, decision_id)

    # --- Propositions ----------------------------------------------------------------------

    def propose(
        self,
        action: str,
        *,
        subject_type: str,
        subject_id: str | None,
        proposal: dict[str, Any],
        proposed_by: str,
        brand: str = DEFAULT_BRAND,
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            return self.propose_in(
                conn,
                action,
                subject_type=subject_type,
                subject_id=subject_id,
                proposal=proposal,
                proposed_by=proposed_by,
                brand=brand,
            )

    def propose_in(
        self,
        conn: Connection,
        action: str,
        *,
        subject_type: str,
        subject_id: str | None,
        proposal: dict[str, Any],
        proposed_by: str,
        brand: str = DEFAULT_BRAND,
    ) -> dict[str, Any]:
        """Enregistre une proposition dans la transaction de l'appelant."""
        brand_id = conn.execute(
            text("SELECT id FROM media_brand WHERE slug = :s"), {"s": brand}
        ).scalar_one_or_none()
        if brand_id is None:
            raise GovernanceError(f"marque inconnue : {brand}")
        policy = (
            conn.execute(
                text(
                    "SELECT requires_approval, version FROM editorial_policy "
                    "WHERE brand_id = :b AND action = :a"
                ),
                {"b": brand_id, "a": action},
            )
            .mappings()
            .one_or_none()
        )
        required = action in ALWAYS_APPROVED or policy is None or policy["requires_approval"]
        decision_id: UUID = conn.execute(
            text(
                "INSERT INTO editorial_decision (brand_id, action, subject_type, subject_id, "
                "proposal, proposed_by, policy_version) VALUES (:b, :a, :t, :sid, "
                "CAST(:p AS jsonb), :by, :v) RETURNING id"
            ),
            {
                "b": brand_id,
                "a": action,
                "t": subject_type,
                "sid": subject_id,
                "p": _json(proposal),
                "by": proposed_by,
                "v": policy["version"] if policy else None,
            },
        ).scalar_one()
        if not required:
            self._apply(conn, decision_id, decided_by="POLICY", reason="politique : automatique")
        return {"decision_id": decision_id, "status": "PROPOSED" if required else "APPROVED"}

    def propose_pillar(
        self, name: str, description: str, *, rules: dict[str, Any], proposed_by: str
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            brand_id = conn.execute(
                text("SELECT id FROM media_brand WHERE slug = :s"), {"s": DEFAULT_BRAND}
            ).scalar_one()
            if conn.execute(
                text("SELECT 1 FROM editorial_pillar WHERE brand_id = :b AND name = :n"),
                {"b": brand_id, "n": name},
            ).first():
                raise GovernanceError(f"pilier déjà défini : {name}")
            pillar_id = conn.execute(
                text(
                    "INSERT INTO editorial_pillar (brand_id, name, description, rules) VALUES "
                    "(:b, :n, :d, CAST(:r AS jsonb)) RETURNING id"
                ),
                {"b": brand_id, "n": name, "d": description, "r": _json(rules)},
            ).scalar_one()
            return self.propose_in(
                conn,
                "PILLAR_CHANGE",
                subject_type="editorial_pillar",
                subject_id=str(pillar_id),
                proposal={"op": "create", "name": name, "description": description},
                proposed_by=proposed_by,
            ) | {"pillar_id": pillar_id}

    def propose_policy(
        self, action: str, requires_approval: bool, *, note: str | None, proposed_by: str
    ) -> dict[str, Any]:
        if action in ALWAYS_APPROVED and not requires_approval:
            raise GovernanceError(f"{action} exige toujours l'approbation du fondateur")
        return self.propose(
            "POLICY_CHANGE",
            subject_type="editorial_policy",
            subject_id=action,
            proposal={"action": action, "requires_approval": requires_approval, "note": note},
            proposed_by=proposed_by,
        )

    # --- Décisions du fondateur ------------------------------------------------------------

    @staticmethod
    def _require_founder(role: str) -> None:
        if role != FOUNDER:
            raise GovernanceError("seul le fondateur décide ; un agent ne peut que proposer")

    def approve(self, decision_id: UUID, *, decided_by: str, role: str) -> dict[str, Any]:
        self._require_founder(role)
        with self._engine.begin() as conn:
            self._apply(conn, decision_id, decided_by=decided_by, reason=None)
            return self._load(conn, decision_id)

    def reject(
        self, decision_id: UUID, *, decided_by: str, role: str, reason: str
    ) -> dict[str, Any]:
        self._require_founder(role)
        if not reason.strip():
            raise GovernanceError("un rejet exige un motif")
        with self._engine.begin() as conn:
            decision = self._load(conn, decision_id, lock=True)
            if decision["status"] != "PROPOSED":
                raise GovernanceError(f"décision déjà {decision['status']}")
            if decision["action"] == "PILLAR_CHANGE" and decision["proposal"]["op"] == "create":
                conn.execute(
                    text("UPDATE editorial_pillar SET status = 'RETIRED' WHERE id = :id"),
                    {"id": decision["subject_id"]},
                )
            self._close(conn, decision_id, "REJECTED", decided_by, reason)
            return self._load(conn, decision_id)

    def revert(
        self, decision_id: UUID, *, decided_by: str, role: str, reason: str
    ) -> dict[str, Any]:
        self._require_founder(role)
        if not reason.strip():
            raise GovernanceError("une annulation exige un motif")
        with self._engine.begin() as conn:
            decision = self._load(conn, decision_id, lock=True)
            if decision["status"] != "APPROVED":
                raise GovernanceError("seule une décision approuvée peut être annulée")
            handler = _HANDLERS.get(decision["action"])
            if handler is not None:
                handler(conn, decision, False)
            self._close(conn, decision_id, "REVERTED", decided_by, reason)
            return self._load(conn, decision_id)

    # --- Interne ---------------------------------------------------------------------------

    def _apply(
        self, conn: Connection, decision_id: UUID, *, decided_by: str, reason: str | None
    ) -> None:
        decision = self._load(conn, decision_id, lock=True)
        if decision["status"] != "PROPOSED":
            raise GovernanceError(f"décision déjà {decision['status']}")
        decision["decided_by"] = decided_by
        handler = _HANDLERS.get(decision["action"])
        previous = handler(conn, decision, True) if handler is not None else None
        if previous is not None:
            conn.execute(
                text(
                    "UPDATE editorial_decision SET proposal = proposal || "
                    "jsonb_build_object('previous', CAST(:p AS jsonb)) WHERE id = :id"
                ),
                {"p": _json(previous), "id": decision_id},
            )
        self._close(conn, decision_id, "APPROVED", decided_by, reason)

    @staticmethod
    def _close(
        conn: Connection, decision_id: UUID, status: str, decided_by: str, reason: str | None
    ) -> None:
        conn.execute(
            text(
                "UPDATE editorial_decision SET status = :s, decided_by = :by, decided_at = now(), "
                "reason = COALESCE(:r, reason) WHERE id = :id"
            ),
            {"s": status, "by": decided_by, "r": reason, "id": decision_id},
        )

    @staticmethod
    def _load(conn: Connection, decision_id: UUID, *, lock: bool = False) -> dict[str, Any]:
        row = (
            conn.execute(
                text(_LOAD_LOCKED if lock else _LOAD),
                {"id": decision_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise GovernanceError("décision inconnue")
        return dict(row)
