"""Ligne de commande du moteur d'émissions (gratuite, aucune publication).

primestone-shows show SERIES_ID                    (règles, formats, épisodes, conformité)
primestone-shows transition SERIES_ID TESTING|ACTIVE|SUSPENDED|RETIRED [--reason …]
primestone-shows guidelines SERIES_ID changes.json (nouvelle version des règles, proposée)
primestone-shows history SERIES_ID                 (versions des règles et décisions)
primestone-shows format SERIES_ID format.json      (nom, plateforme, langue, durées, structure)
primestone-shows production SERIES_ID NUMBER
primestone-shows final-validation SERIES_ID NUMBER (proposée au fondateur)
primestone-shows published SERIES_ID NUMBER CONTENT_ID   (déclaration, après approbation)
primestone-shows performance SERIES_ID
primestone-shows fit "sujet" [--language fr|en]    (émissions et piliers adaptés)

Les décisions se prennent avec primestone-brand approve|reject|revert.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.shows import ShowService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-shows")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("show", "history", "performance"):
        sub.add_parser(name).add_argument("series_id", type=UUID)
    tr = sub.add_parser("transition")
    tr.add_argument("series_id", type=UUID)
    tr.add_argument("to", choices=["TESTING", "ACTIVE", "SUSPENDED", "RETIRED"])
    tr.add_argument("--reason")
    for name in ("guidelines", "format"):
        p = sub.add_parser(name)
        p.add_argument("series_id", type=UUID)
        p.add_argument("file", type=Path)
    for name in ("production", "final-validation", "published"):
        p = sub.add_parser(name)
        p.add_argument("series_id", type=UUID)
        p.add_argument("number", type=int)
        if name == "published":
            p.add_argument("content_id", type=UUID)
    fit = sub.add_parser("fit")
    fit.add_argument("subject")
    fit.add_argument("--language", choices=["fr", "en"])
    args = parser.parse_args(argv)

    svc = ShowService(create_db_engine(get_settings().database_url))
    out: object
    try:
        if args.command == "show":
            out = svc.show(args.series_id)
        elif args.command == "history":
            out = svc.guidelines(args.series_id)
        elif args.command == "performance":
            out = svc.performance(args.series_id)
        elif args.command == "transition":
            out = svc.transition(
                args.series_id, args.to, proposed_by=args.author, reason=args.reason
            )
        elif args.command == "guidelines":
            changes = json.loads(args.file.read_text(encoding="utf-8"))
            out = svc.propose_guidelines(args.series_id, changes, author=args.author)
        elif args.command == "format":
            fields = json.loads(args.file.read_text(encoding="utf-8"))
            out = {"format_id": str(svc.add_format(args.series_id, **fields))}
        elif args.command == "production":
            svc.start_production(args.series_id, args.number)
            out = {"status": "IN_PRODUCTION"}
        elif args.command == "final-validation":
            out = svc.propose_final_validation(args.series_id, args.number, proposed_by=args.author)
        elif args.command == "published":
            svc.declare_published(args.series_id, args.number, args.content_id)
            out = {"status": "PUBLISHED"}
        else:
            out = svc.fit(args.subject, language=args.language)
    except (LookupError, ValueError) as exc:
        parser.exit(2, f"refusé : {exc}\n")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
