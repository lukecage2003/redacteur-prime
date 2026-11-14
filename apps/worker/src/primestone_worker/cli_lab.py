"""Ligne de commande du laboratoire des théories (gratuite).

primestone-lab create   --documents ID… --title "…" --claim "…" [--subject Selina]
primestone-lab list     [--status OPEN|SUPPORTED|CONTESTED|REFUTED] [--level THEORY|SPECULATION]
primestone-lab show     THEORY_ID
primestone-lab evidence THEORY_ID --role SUPPORTS|REFUTES --document ID --page N
                        [--panel M] [--excerpt "…"] [--level CANON] [--note "…"]
primestone-lab retract  EVIDENCE_ID --reason "…"
primestone-lab alternative THEORY_ID --text "…"
primestone-lab research THEORY_ID          (Theory Researcher : candidats pour/contre)
primestone-lab review   THEORY_ID [--process]   (mission THEORY_REVIEW du Chief Editor)
primestone-lab ask      --documents ID… --question "…" [--process]   (RESEARCH_DOSSIER)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings
from primestone.lab import EVIDENCE_LEVELS, ROLES, lab_from_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-lab")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--documents", nargs="+", type=UUID, required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--claim", required=True)
    create.add_argument("--subject", action="append", default=[])
    listing = sub.add_parser("list")
    listing.add_argument("--status", choices=("OPEN", "SUPPORTED", "CONTESTED", "REFUTED"))
    listing.add_argument("--level", choices=("THEORY", "SPECULATION"))
    sub.add_parser("show").add_argument("theory_id", type=UUID)
    evidence = sub.add_parser("evidence")
    evidence.add_argument("theory_id", type=UUID)
    evidence.add_argument("--role", choices=ROLES, required=True)
    evidence.add_argument("--document", type=UUID, required=True)
    evidence.add_argument("--page", type=int, required=True)
    evidence.add_argument("--panel", type=int)
    evidence.add_argument("--excerpt")
    evidence.add_argument("--level", choices=EVIDENCE_LEVELS, default="CANON")
    evidence.add_argument("--note")
    retract = sub.add_parser("retract")
    retract.add_argument("evidence_id", type=UUID)
    retract.add_argument("--reason", required=True)
    alternative = sub.add_parser("alternative")
    alternative.add_argument("theory_id", type=UUID)
    alternative.add_argument("--text", required=True)
    sub.add_parser("research").add_argument("theory_id", type=UUID)
    review = sub.add_parser("review")
    review.add_argument("theory_id", type=UUID)
    review.add_argument("--process", action="store_true", help="exécuter ici, sans worker")
    ask = sub.add_parser("ask")
    ask.add_argument("--documents", nargs="+", type=UUID, required=True)
    ask.add_argument("--question", required=True)
    ask.add_argument("--process", action="store_true", help="exécuter ici, sans worker")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    lab = lab_from_settings(settings, engine)
    out: object
    if args.command == "create":
        theory_id = lab.create(
            title=args.title,
            claim=args.claim,
            document_ids=args.documents,
            subjects=args.subject,
            author=args.author,
        )
        out = lab.theory(theory_id)
    elif args.command == "list":
        out = lab.theories(status=args.status, level=args.level)
    elif args.command == "show":
        out = lab.theory(args.theory_id)
    elif args.command == "evidence":
        out = lab.add_evidence(
            args.theory_id,
            role=args.role,
            document_id=args.document,
            page=args.page,
            panel=args.panel,
            excerpt=args.excerpt,
            level=args.level,
            note=args.note,
            author=args.author,
        )
    elif args.command == "retract":
        out = lab.retract_evidence(args.evidence_id, author=args.author, reason=args.reason)
    elif args.command == "alternative":
        out = {"id": str(lab.add_alternative(args.theory_id, text_=args.text, author=args.author))}
    elif args.command == "research":
        out = lab.research(args.theory_id, author=args.author)
    else:
        editorial = editorial_service_from_settings(settings, engine)
        if args.command == "review":
            mission_id = editorial.create_mission(
                "THEORY_REVIEW", [], {"theory_id": str(args.theory_id)}
            )
        else:
            mission_id = editorial.create_mission(
                "RESEARCH_DOSSIER", args.documents, {"question": args.question}
            )
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
