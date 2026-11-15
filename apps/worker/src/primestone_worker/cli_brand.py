"""Ligne de commande Brand Intelligence et gouvernance (gratuite).

primestone-brand brands | policies | pillars
primestone-brand decisions [--status PROPOSED]       (journal des décisions)
primestone-brand pillar NAME "description" [--rules rules.json]   (proposition)
primestone-brand policy ACTION --required|--automatic [--note …]  (proposition)
primestone-brand bootstrap                           (piliers et 4 émissions proposés)
primestone-brand approve DECISION_ID
primestone-brand reject DECISION_ID --reason "…"
primestone-brand revert DECISION_ID --reason "…"

Exécutée par le propriétaire : ses décisions portent le rôle FOUNDER.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.governance import FOUNDER, GovernanceError, GovernanceService
from primestone.shows.starter import bootstrap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-brand")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("brands", "policies", "pillars", "bootstrap"):
        sub.add_parser(name)
    sub.add_parser("decisions").add_argument("--status")
    pillar = sub.add_parser("pillar")
    pillar.add_argument("name")
    pillar.add_argument("description")
    pillar.add_argument("--rules", type=Path)
    policy = sub.add_parser("policy")
    policy.add_argument("action")
    mode = policy.add_mutually_exclusive_group(required=True)
    mode.add_argument("--required", action="store_true")
    mode.add_argument("--automatic", action="store_true")
    policy.add_argument("--note")
    for name in ("approve", "reject", "revert"):
        decide = sub.add_parser(name)
        decide.add_argument("decision_id", type=UUID)
        if name != "approve":
            decide.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    engine = create_db_engine(get_settings().database_url)
    svc = GovernanceService(engine)
    out: object
    try:
        if args.command == "brands":
            out = svc.brands()
        elif args.command == "policies":
            out = svc.policies()
        elif args.command == "pillars":
            out = svc.pillars()
        elif args.command == "bootstrap":
            out = bootstrap(engine, proposed_by=args.author)
        elif args.command == "decisions":
            out = svc.decisions(args.status)
        elif args.command == "pillar":
            rules = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else {}
            out = svc.propose_pillar(
                args.name, args.description, rules=rules, proposed_by=args.author
            )
        elif args.command == "policy":
            out = svc.propose_policy(
                args.action, args.required, note=args.note, proposed_by=args.author
            )
        elif args.command == "approve":
            out = svc.approve(args.decision_id, decided_by=args.author, role=FOUNDER)
        elif args.command == "reject":
            out = svc.reject(
                args.decision_id, decided_by=args.author, role=FOUNDER, reason=args.reason
            )
        else:
            out = svc.revert(
                args.decision_id, decided_by=args.author, role=FOUNDER, reason=args.reason
            )
    except GovernanceError as exc:
        parser.exit(2, f"refusé : {exc}\n")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
