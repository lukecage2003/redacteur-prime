"""Ligne de commande de la bibliothèque.

primestone-library import DOSSIER_OU_FICHIERS… [--process] [--workers N]
primestone-library status RUN_ID
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

from primestone.comic import ImportSource, library_service_from_settings
from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.jobs import PostgresJobQueue
from primestone_worker.main import Worker, build_registry

SUFFIXES = {".pdf", ".cbz"}


def collect(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.suffix.lower() in SUFFIXES))
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f"introuvable : {path}")
    return files


async def drain(queue: PostgresJobQueue, worker_count: int, run_id: UUID) -> None:
    """Traite la file dans ce processus jusqu'à la fin du lot (usage local)."""
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    registry = build_registry(settings, engine)
    workers = [Worker(queue, registry, worker_id=f"cli-{i}") for i in range(worker_count)]

    async def loop(worker: Worker) -> None:
        while queue.run_status(run_id) in ("PENDING", "RUNNING"):
            if not await worker.run_once():
                await asyncio.sleep(0.2)

    await asyncio.gather(*(loop(w) for w in workers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-library")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="importer des PDF/CBZ (fichiers ou dossiers)")
    imp.add_argument("paths", nargs="+", type=Path)
    imp.add_argument("--label")
    imp.add_argument("--process", action="store_true", help="traiter le lot dans ce processus")
    imp.add_argument("--workers", type=int, default=4)
    st = sub.add_parser("status", help="rapport d'un lot")
    st.add_argument("run_id", type=UUID)
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(level=logging.WARNING)
    engine = create_db_engine(settings.database_url)
    service = library_service_from_settings(settings, engine)

    if args.command == "import":
        files = collect(args.paths)
        result = service.start_import(
            [ImportSource(path=f, filename=f.name) for f in files], label=args.label
        )
        print(f"lot {result.run_id} : {len(files)} fichier(s)", file=sys.stderr)
        if args.process:
            asyncio.run(drain(PostgresJobQueue(engine), args.workers, result.run_id))
        run_id = result.run_id
    else:
        run_id = args.run_id

    report = service.batch_report(run_id)
    if report is None:
        print("lot introuvable", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
