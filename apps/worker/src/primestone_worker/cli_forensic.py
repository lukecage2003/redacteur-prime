"""Ligne de commande forensique (gratuite : aucun modèle n'est appelé).

    primestone-forensic analyze --documents ID… [--character NOM…]
    primestone-forensic report  --documents ID…
    primestone-forensic observations --documents ID… [--kind CLAIM] [--level CANON] [--subject NOM]

L'ordre des documents compte : donner les tomes dans l'ordre de lecture.
"""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.forensic import forensic_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-forensic")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("analyze", "report", "observations"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--documents", nargs="+", type=UUID, required=True)
        if name == "analyze":
            cmd.add_argument("--character", action="append", default=[], help="nom connu")
        if name == "observations":
            cmd.add_argument("--kind")
            cmd.add_argument("--level")
            cmd.add_argument("--subject")
    args = parser.parse_args(argv)

    service = forensic_service(create_db_engine(get_settings().database_url))
    out: object
    if args.command == "analyze":
        run_id, stats = service.analyze(args.documents, set(args.character))
        out = {"run_id": str(run_id), **stats, "report": service.report(args.documents)}
    elif args.command == "report":
        out = service.report(args.documents)
    else:
        out = service.observations(
            args.documents, kind=args.kind, level=args.level, subject=args.subject
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
