"""Chief Editor : missions durables, délégation aux agents, confrontation, approbation humaine.

Cycle d'une mission : PLANNED → RUNNING → AWAITING_APPROVAL → APPROVED | REJECTED
(ou FAILED si une tâche critique échoue). Chaque tâche est persistée : une mission interrompue
reprend là où elle s'était arrêtée. Une tâche est tentée deux fois ; un échec non critique
dégrade le livrable (signalé), un échec critique arrête la mission.
Un livrable avec une erreur factuelle majeure (Fact Checker FAIL) ne peut pas être approuvé.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.ai_gateway import AIGateway, CompletionRequest, LLMProvider, Message
from primestone.editorial.agents import (
    AGENTS,
    MISSION_TYPES,
    WRITER_PROMPT_ID,
    WRITER_PROMPT_VERSION,
    MissionContext,
    plan,
    theory_recommendation,
)
from primestone.forensic import ForensicService
from primestone.jobs import PermanentError, PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.lab import TheoryLab

RUN_STEP = "editorial.run_mission"
RUN_KIND = "editorial.mission"
MAX_ATTEMPTS = 2


class EditorialError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class EditorialService:
    def __init__(
        self,
        engine: Engine,
        forensic: ForensicService,
        knowledge: KnowledgeService,
        queue: PostgresJobQueue,
        writer_provider: Callable[[], LLMProvider] | None = None,
        lab: TheoryLab | None = None,
    ) -> None:
        self._lab = lab
        self._engine = engine
        self._forensic = forensic
        self._knowledge = knowledge
        self._queue = queue
        self._writer_provider = writer_provider

    # --- Agents ------------------------------------------------------------------------------

    @staticmethod
    def agents() -> list[dict[str, Any]]:
        return [
            {
                "key": a.key,
                "name": a.name,
                "role": a.role,
                "limits": a.limits,
                "phase": a.phase,
                "available": a.available,
            }
            for a in AGENTS.values()
        ]

    # --- Création ----------------------------------------------------------------------------

    def create_mission(
        self,
        mission_type: str,
        document_ids: Sequence[UUID],
        params: dict[str, Any],
        *,
        title: str | None = None,
    ) -> UUID:
        if mission_type not in MISSION_TYPES:
            raise EditorialError(f"type de mission inconnu : {mission_type}")
        theory = None
        if mission_type == "THEORY_REVIEW":
            if self._lab is None:
                raise EditorialError("laboratoire des théories non configuré")
            try:
                theory = self._lab.theory(UUID(str(params.get("theory_id"))))
            except ValueError:
                theory = None
            if theory is None:
                raise EditorialError("théorie introuvable")
            document_ids = document_ids or [UUID(d) for d in theory["document_ids"]]
        if not document_ids:
            raise EditorialError("au moins un document est requis")
        try:
            tasks = plan(mission_type, params)
        except ValueError as exc:
            raise EditorialError(str(exc)) from None
        with self._engine.connect() as conn:
            known = conn.execute(
                text("SELECT count(*) FROM document WHERE id = ANY(:ids)"),
                {"ids": list(document_ids)},
            ).scalar_one()
        if known != len(set(document_ids)):
            raise EditorialError("document inconnu dans la mission")
        run_id = self._queue.create_run(RUN_KIND, {"type": mission_type})
        default_title = {
            "CHARACTER_DOSSIER": f"Dossier : {params.get('character', '')}",
            "CONTINUITY_AUDIT": "Audit de continuité",
            "FACT_CHECK": "Vérification d'un texte",
            "THEORY_REVIEW": f"Revue de théorie : {theory['title'] if theory else ''}",
            "RESEARCH_DOSSIER": f"Recherche : {params.get('question', '')}",
        }[mission_type]
        with self._engine.begin() as conn:
            mission_id: UUID = conn.execute(
                text(
                    "INSERT INTO mission (type, title, document_ids, params, run_id) "
                    "VALUES (:t, :title, CAST(:docs AS jsonb), CAST(:p AS jsonb), :run) "
                    "RETURNING id"
                ),
                {
                    "t": mission_type,
                    "title": title or default_title,
                    "docs": _json([str(d) for d in document_ids]),
                    "p": _json(params),
                    "run": run_id,
                },
            ).scalar_one()
            for position, task in enumerate(tasks, start=1):
                conn.execute(
                    text(
                        "INSERT INTO mission_task "
                        "(mission_id, position, key, agent, critical, input) "
                        "VALUES (:m, :pos, :key, :agent, :critical, CAST(:input AS jsonb))"
                    ),
                    {
                        "m": mission_id,
                        "pos": position,
                        "key": task.key,
                        "agent": task.agent,
                        "critical": task.critical,
                        "input": _json(task.inputs),
                    },
                )
        self._queue.enqueue(
            run_id,
            RUN_STEP,
            {"mission_id": str(mission_id)},
            idempotency_key=f"mission:{mission_id}",
        )
        return mission_id

    # --- Exécution (étape durable du worker) ---------------------------------------------------

    def _writer(self) -> Callable[[str, str], Awaitable[tuple[str, dict[str, Any]]]] | None:
        if self._writer_provider is None:
            return None
        gateway = AIGateway(self._writer_provider(), Decimal("0"), zero_cost=True)

        async def write(system: str, draft: str) -> tuple[str, dict[str, Any]]:
            result = await gateway.complete(
                CompletionRequest(
                    prompt_id=WRITER_PROMPT_ID,
                    prompt_version=WRITER_PROMPT_VERSION,
                    system=system,
                    messages=[Message(role="user", content=draft)],
                    max_output_tokens=4000,
                    temperature=0.2,
                )
            )
            record = gateway.records[-1]
            return result.text, {
                "provider": result.provider,
                "model": result.model,
                "prompt_id": WRITER_PROMPT_ID,
                "prompt_version": WRITER_PROMPT_VERSION,
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cost_usd": str(result.usage.cost_usd),
                "latency_ms": record.latency_ms,
            }

        return write

    def _context(self, mission: dict[str, Any]) -> MissionContext:
        document_ids = [UUID(d) for d in mission["document_ids"]]
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT d.id, c.title, d.page_count FROM document d "
                    "JOIN comic c ON c.id = d.comic_id WHERE d.id = ANY(:ids)"
                ),
                {"ids": document_ids},
            ).all()
        return MissionContext(
            mission_id=mission["id"],
            mission_type=mission["type"],
            document_ids=document_ids,
            params=mission["params"],
            forensic=self._forensic,
            knowledge=self._knowledge,
            titles={r[0]: r[1] for r in rows},
            page_counts={r[0]: r[2] or 0 for r in rows},
            writer=self._writer(),
            lab=self._lab,
        )

    def _set_mission(self, mission_id: UUID, **fields: Any) -> None:
        sets = ", ".join(
            f"{k} = CAST(:{k} AS jsonb)" if k == "result" else f"{k} = :{k}" for k in fields
        )
        values = {k: _json(v) if k == "result" else v for k, v in fields.items()}
        with self._engine.begin() as conn:
            conn.execute(
                text(f"UPDATE mission SET {sets}, updated_at = now() WHERE id = :id"),  # noqa: S608
                {**values, "id": mission_id},
            )

    def _set_task(self, task_id: UUID, **fields: Any) -> None:
        sets = ", ".join(
            f"{k} = CAST(:{k} AS jsonb)" if k == "output" else f"{k} = :{k}" for k in fields
        )
        values = {k: _json(v) if k == "output" else v for k, v in fields.items()}
        with self._engine.begin() as conn:
            conn.execute(
                text(f"UPDATE mission_task SET {sets} WHERE id = :id"),  # noqa: S608
                {**values, "id": task_id},
            )

    async def run_mission(self, payload: dict[str, Any]) -> dict[str, Any]:
        mission_id = UUID(payload["mission_id"])
        mission = self._mission_row(mission_id)
        if mission["status"] in ("AWAITING_APPROVAL", "APPROVED", "REJECTED", "FAILED"):
            return {"skipped": mission["status"]}
        self._set_mission(mission_id, status="RUNNING")
        ctx = self._context(mission)
        for task in self._tasks(mission_id):
            if task["status"] == "SUCCEEDED":  # reprise : résultat déjà acquis
                ctx.outputs[task["key"]] = task["output"]
                continue
            spec = AGENTS[task["agent"]]
            if spec.run is None:
                raise PermanentError(f"agent indisponible : {spec.name} (phase {spec.phase})")
            error = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                self._set_task(
                    task["id"], status="RUNNING", attempts=attempt, started_at=datetime.now(UTC)
                )
                try:
                    output = await spec.run(ctx, task["input"])
                except Exception as exc:  # l'échec d'un agent est géré, jamais masqué
                    error = f"{type(exc).__name__}: {exc}"
                    continue
                ctx.outputs[task["key"]] = output
                self._set_task(
                    task["id"],
                    status="SUCCEEDED",
                    output=output,
                    error=None,
                    finished_at=datetime.now(UTC),
                )
                self._record_agent_run(task["id"], task["agent"], output)
                error = None
                break
            if error is None:
                continue
            self._set_task(task["id"], status="FAILED", error=error, finished_at=datetime.now(UTC))
            if task["critical"]:
                with self._engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE mission_task SET status = 'SKIPPED' "
                            "WHERE mission_id = :m AND status = 'PENDING'"
                        ),
                        {"m": mission_id},
                    )
                self._set_mission(
                    mission_id,
                    status="FAILED",
                    error=f"{spec.name} : {error}",
                    completed_at=datetime.now(UTC),
                )
                raise PermanentError(f"tâche critique en échec : {spec.name}")
        result = self._review(ctx, self._tasks(mission_id))
        self._set_mission(mission_id, status="AWAITING_APPROVAL", result=result)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO approval_request (mission_id, kind, summary, recommendation) "
                    "VALUES (:m, 'MISSION_VALIDATION', :s, :r)"
                ),
                {"m": mission_id, "s": result["summary"], "r": result["recommendation"]},
            )
        return {"recommendation": result["recommendation"]}

    def _record_agent_run(self, task_id: UUID, agent: str, output: dict[str, Any]) -> None:
        call = output.get("writer") if isinstance(output, dict) else None
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO agent_run (mission_task_id, agent, provider, model, prompt_id,
                           prompt_version, input_tokens, output_tokens, cost_usd, latency_ms, error)
                    VALUES (:t, :agent, :provider, :model, :pid, :pver, :tin, :tout, :cost,
                            :lat, :err)
                    """
                ),
                {
                    "t": task_id,
                    "agent": agent,
                    "provider": (call or {}).get("provider") or "deterministe",
                    "model": (call or {}).get("model"),
                    "pid": (call or {}).get("prompt_id"),
                    "pver": (call or {}).get("prompt_version"),
                    "tin": (call or {}).get("input_tokens", 0),
                    "tout": (call or {}).get("output_tokens", 0),
                    "cost": Decimal(str((call or {}).get("cost_usd", "0"))),
                    "lat": (call or {}).get("latency_ms"),
                    "err": None if not call or call.get("accepted", True) else call.get("reason"),
                },
            )

    def _review(self, ctx: MissionContext, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """Confrontation des résultats des agents et recommandation du Chief Editor."""
        findings: list[str] = []
        prepare = ctx.outputs.get("prepare", {})
        missing = {k: v for k, v in prepare.get("missing_pages", {}).items() if v}
        for doc_id, pages in missing.items():
            title = ctx.titles.get(UUID(doc_id), doc_id)
            findings.append(f"Pages non transcrites dans {title} : {', '.join(map(str, pages))}.")
        for t in tasks:
            if t["status"] == "FAILED":
                findings.append(
                    f"{AGENTS[t['agent']].name} en échec ({t['error']}) : livrable dégradé."
                )
        synthesis = ctx.outputs.get("synthesis", {})
        writer = synthesis.get("writer")
        if writer and not writer.get("accepted"):
            findings.append(
                f"Rédaction par modèle écartée : {writer.get('reason')} ; gabarit conservé."
            )
        continuity = ctx.outputs.get("continuity", {})
        if continuity.get("contradictions"):
            findings.append(
                f"{len(continuity['contradictions'])} contradiction(s) candidate(s) "
                "à trancher par un humain."
            )
        research = ctx.outputs.get("character_research")
        if research and not any(
            r["type"] == "APPEARS_IN" and r["level"] == "CANON" for r in research["relations"]
        ):
            findings.append(
                "Aucune présence du personnage attestée en CANON (attributions à valider)."
            )
        reviewed = ctx.outputs.get("theory_research")
        if reviewed:
            findings.append(f"Théorie : {theory_recommendation(reviewed['theory'])}.")
        searched = ctx.outputs.get("research", {}).get("search")
        if searched is not None and not searched["passages"] and not searched["observations"]:
            findings.append("Aucune source trouvée dans les pages transcrites.")
        check = ctx.outputs.get("fact_check", {})
        verdict = check.get("verdict", "NEEDS_REVIEW")
        if verdict == "FAIL":
            recommendation = "NE PAS VALIDER"
            findings.insert(0, "Erreur factuelle majeure relevée par le Fact Checker.")
        elif verdict == "NEEDS_REVIEW" or missing or any(t["status"] == "FAILED" for t in tasks):
            recommendation = "VALIDER AVEC RÉSERVES"
        else:
            recommendation = "VALIDER"
        counts = check.get("counts", {})
        summary = (
            f"Fact Checker : {verdict} ({counts.get('VERIFIED', 0)} citation(s) vérifiée(s)). "
            + " ".join(findings[:3])
        )
        return {
            "recommendation": recommendation,
            "summary": summary.strip(),
            "findings": findings,
            "deliverable": synthesis.get("text") or ctx.params.get("draft"),
            "author": synthesis.get("author", "texte fourni"),
            "fact_check": check,
        }

    # --- Décision humaine --------------------------------------------------------------------

    def decide(self, approval_id: UUID, *, approve: bool, author: str, comment: str | None) -> None:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT a.status, a.mission_id, m.result FROM approval_request a "
                    "JOIN mission m ON m.id = a.mission_id WHERE a.id = :id FOR UPDATE"
                ),
                {"id": approval_id},
            ).one_or_none()
            if row is None:
                raise LookupError("demande d'approbation introuvable")
            status, mission_id, result = row
            if status != "PENDING":
                raise EditorialError("demande déjà traitée")
            if approve and (result or {}).get("fact_check", {}).get("verdict") == "FAIL":
                raise EditorialError(
                    "validation impossible : erreur factuelle majeure (corriger puis relancer)"
                )
            decision = "APPROVED" if approve else "REJECTED"
            conn.execute(
                text(
                    "UPDATE approval_request SET status = :s, decided_by = :a, comment = :c, "
                    "decided_at = now() WHERE id = :id"
                ),
                {"s": decision, "a": author, "c": comment, "id": approval_id},
            )
            conn.execute(
                text(
                    "UPDATE mission SET status = :s, completed_at = now(), updated_at = now() "
                    "WHERE id = :m"
                ),
                {"s": decision, "m": mission_id},
            )

    # --- Lecture -----------------------------------------------------------------------------

    def _mission_row(self, mission_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(text("SELECT * FROM mission WHERE id = :id"), {"id": mission_id})
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError("mission introuvable")
        return dict(row)

    def _tasks(self, mission_id: UUID) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text("SELECT * FROM mission_task WHERE mission_id = :m ORDER BY position"),
                    {"m": mission_id},
                ).mappings()
            ]

    def missions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT id, type, title, status, created_at, completed_at, "
                        "result->>'recommendation' AS recommendation FROM mission "
                        "ORDER BY created_at DESC LIMIT :l"
                    ),
                    {"l": limit},
                )
                .mappings()
                .all()
            )
        return [
            {
                **dict(r),
                "id": str(r["id"]),
                "created_at": r["created_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]

    def mission(self, mission_id: UUID) -> dict[str, Any]:
        mission = self._mission_row(mission_id)
        with self._engine.connect() as conn:
            approvals = (
                conn.execute(
                    text(
                        "SELECT id, kind, summary, recommendation, status, decided_by, comment, "
                        "decided_at FROM approval_request WHERE mission_id = :m ORDER BY created_at"
                    ),
                    {"m": mission_id},
                )
                .mappings()
                .all()
            )
            runs = (
                conn.execute(
                    text(
                        "SELECT r.agent, r.provider, r.model, r.prompt_id, r.prompt_version, "
                        "r.input_tokens, r.output_tokens, r.cost_usd, r.error FROM agent_run r "
                        "JOIN mission_task t ON t.id = r.mission_task_id WHERE t.mission_id = :m "
                        "ORDER BY r.created_at"
                    ),
                    {"m": mission_id},
                )
                .mappings()
                .all()
            )
        return {
            "id": str(mission["id"]),
            "type": mission["type"],
            "title": mission["title"],
            "status": mission["status"],
            "document_ids": mission["document_ids"],
            "params": mission["params"],
            "result": mission["result"],
            "error": mission["error"],
            "tasks": [
                {
                    "position": t["position"],
                    "key": t["key"],
                    "agent": t["agent"],
                    "agent_name": AGENTS[t["agent"]].name,
                    "critical": t["critical"],
                    "status": t["status"],
                    "attempts": t["attempts"],
                    "error": t["error"],
                }
                for t in self._tasks(mission_id)
            ],
            "approvals": [
                {
                    **dict(a),
                    "id": str(a["id"]),
                    "decided_at": a["decided_at"].isoformat() if a["decided_at"] else None,
                }
                for a in approvals
            ],
            "agent_runs": [{**dict(r), "cost_usd": str(r["cost_usd"])} for r in runs],
        }
