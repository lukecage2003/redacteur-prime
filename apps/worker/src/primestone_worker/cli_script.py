"""Ligne de commande Maximum Storytelling (gratuite).

primestone-script list | show ID
primestone-script create --title "…" --language fr|en FICHIER [--documents ID…]   (.md/.txt/.pdf)
primestone-script version ID FICHIER
primestone-script step ID ETAPE [--reason "…"]       (BRIEF … ADAPTATION ; retour possible)
primestone-script evaluate ID                         (Fact Checker + note sur 100, veto)
primestone-script review ID [--process]               (mission SCRIPT_REVIEW du Chief Editor)
primestone-script validate ID                         (validation finale humaine)
primestone-script adapt ID FICHIER [--title "…"]      (version dans l'autre langue)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.db.schema import SCRIPT_STEPS
from primestone.editorial import editorial_service_from_settings
from primestone.storytelling import read_script_file, storytelling_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-script")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("show", "evaluate", "validate"):
        sub.add_parser(name).add_argument("script_id", type=UUID)
    create = sub.add_parser("create")
    create.add_argument("file", type=Path)
    create.add_argument("--title", required=True)
    create.add_argument("--language", choices=("fr", "en"), required=True)
    create.add_argument("--documents", nargs="*", type=UUID, default=[])
    version = sub.add_parser("version")
    version.add_argument("script_id", type=UUID)
    version.add_argument("file", type=Path)
    step = sub.add_parser("step")
    step.add_argument("script_id", type=UUID)
    step.add_argument("step", choices=SCRIPT_STEPS[:-1])
    step.add_argument("--reason")
    review = sub.add_parser("review")
    review.add_argument("script_id", type=UUID)
    review.add_argument("--process", action="store_true")
    adapt = sub.add_parser("adapt")
    adapt.add_argument("script_id", type=UUID)
    adapt.add_argument("file", type=Path)
    adapt.add_argument("--title")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    svc = storytelling_service(engine)
    out: object
    if args.command == "list":
        out = svc.scripts()
    elif args.command == "show":
        out = svc.script(args.script_id)
    elif args.command == "create":
        out = {
            "script_id": str(
                svc.create(
                    title=args.title,
                    language=args.language,
                    content=read_script_file(args.file),
                    author=args.author,
                    document_ids=args.documents,
                    origin="IMPORT",
                )
            )
        }
    elif args.command == "version":
        out = svc.add_version(
            args.script_id, read_script_file(args.file), author=args.author, origin="IMPORT"
        )
    elif args.command == "step":
        svc.move(args.script_id, args.step, author=args.author, reason=args.reason)
        out = {"step": args.step}
    elif args.command == "evaluate":
        out = svc.evaluate(args.script_id)
    elif args.command == "validate":
        svc.validate(args.script_id, author=args.author)
        out = {"validated": str(args.script_id)}
    elif args.command == "adapt":
        out = {
            "script_id": str(
                svc.adapt(
                    args.script_id,
                    content=read_script_file(args.file),
                    title=args.title,
                    author=args.author,
                )
            )
        }
    else:
        editorial = editorial_service_from_settings(settings, engine)
        mission_id = editorial.create_mission(
            "SCRIPT_REVIEW", [], {"script_id": str(args.script_id)}
        )
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
