"""Ligne de commande Performance Intelligence (chaîne Primestone, gratuite).

primestone-performance import export.csv [--from 2026-10-01 --to 2026-10-31]
primestone-performance contents
primestone-performance link CONTENT_ID SCRIPT_ID [--language fr|en]
primestone-performance report [--min-items 5]
primestone-performance review [--process]     (mission PERFORMANCE_REVIEW)
primestone-performance authorize [--port 8765]   (OAuth de TA chaîne, lecture seule, gratuit)
primestone-performance sync --from 2026-10-01 --to 2026-10-31 [--curves 10]
primestone-performance objective CONTENT_ID --objective DISCOVERY [--format LONG]
primestone-performance objectives | experiments
primestone-performance experiment-create --title … --hypothesis … --variable TITLE --metric ctr
primestone-performance experiment-variant EXP_ID --label A --description …
                       (--exposures N --successes S | --share 0.55) [--source …]
primestone-performance experiment-conclude EXP_ID [--conclusion …] [--next …]
primestone-performance autopsy CONTENT_ID | hooks | drop-offs | returning | validation
primestone-performance loop SCRIPT_ID
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from primestone.config import Settings, get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings
from primestone.performance import (
    AnalyticsClient,
    PerformanceLab,
    PerformanceService,
    access_token_provider,
    consent_url,
)
from primestone.performance.oauth import exchange_code

OBJECTIVES = ("DISCOVERY", "EXPLORATION", "EXPERTISE", "COMMUNITY")
FORMATS = ("LONG", "SHORT", "REEL", "CAROUSEL", "POST", "PODCAST", "LIVE")
VARIABLES = ("TITLE", "THUMBNAIL", "HOOK", "PROMISE", "FORMAT", "LENGTH", "OTHER")


def _oauth_client(settings: Settings) -> tuple[str, str]:
    if not settings.youtube_oauth_client_id or not settings.youtube_oauth_client_secret:
        raise SystemExit(
            "Définir PRIMESTONE_YOUTUBE_OAUTH_CLIENT_ID et _CLIENT_SECRET (client OAuth "
            "« application de bureau », voir docs/modules/performance.md)."
        )
    return settings.youtube_oauth_client_id, settings.youtube_oauth_client_secret.get_secret_value()


def _authorize(settings: Settings, port: int) -> dict[str, str]:
    """Flux loopback : ouvre l'URL, reçoit le code sur 127.0.0.1, affiche le jeton UNE fois."""
    client_id, secret = _oauth_client(settings)
    redirect = f"http://127.0.0.1:{port}"
    url, state = consent_url(client_id, redirect)
    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = parse_qs(urlparse(self.path).query)
            received.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Autorisation reçue : vous pouvez fermer cet onglet.".encode())

        def log_message(self, *args: object) -> None:  # aucun journal (le code est sensible)
            return

    print(f"Ouvrez cette adresse et autorisez l'accès en lecture :\n{url}", file=sys.stderr)
    with HTTPServer(("127.0.0.1", port), Handler) as server:
        server.handle_request()
    if received.get("state") != state or "code" not in received:
        raise SystemExit("autorisation refusée ou état invalide")
    token = exchange_code(client_id, secret, received["code"], redirect)
    print(
        "Ajoutez cette ligne à votre .env (ou Secret Manager), puis ne la partagez pas :\n"
        f"PRIMESTONE_YOUTUBE_OAUTH_REFRESH_TOKEN={token}",
        file=sys.stderr,
    )
    return {"status": "autorisé"}


def _analytics(settings: Settings) -> AnalyticsClient:
    client_id, secret = _oauth_client(settings)
    if not settings.youtube_oauth_refresh_token:
        raise SystemExit("Lancer d'abord : primestone-performance authorize")
    return AnalyticsClient(
        access_token_provider(
            client_id, secret, settings.youtube_oauth_refresh_token.get_secret_value()
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-performance")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("file", type=Path)
    imp.add_argument("--from", dest="start", type=date.fromisoformat)
    imp.add_argument("--to", dest="end", type=date.fromisoformat)
    sub.add_parser("contents")
    link = sub.add_parser("link")
    link.add_argument("content_id", type=UUID)
    link.add_argument("script_id", type=UUID)
    link.add_argument("--language", choices=("fr", "en"))
    report = sub.add_parser("report")
    report.add_argument("--min-items", type=int, default=5)
    sub.add_parser("review").add_argument("--process", action="store_true")
    sub.add_parser("authorize").add_argument("--port", type=int, default=8765)
    sync = sub.add_parser("sync")
    sync.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    sync.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    sync.add_argument("--curves", type=int, default=10)
    objective = sub.add_parser("objective")
    objective.add_argument("content_id", type=UUID)
    objective.add_argument("--objective", choices=OBJECTIVES)
    objective.add_argument("--format", choices=FORMATS)
    sub.add_parser("objectives")
    sub.add_parser("experiments")
    create = sub.add_parser("experiment-create")
    for name in ("title", "hypothesis", "metric"):
        create.add_argument(f"--{name}", required=True)
    create.add_argument("--variable", choices=VARIABLES, required=True)
    create.add_argument("--audience")
    variant = sub.add_parser("experiment-variant")
    variant.add_argument("experiment_id", type=UUID)
    variant.add_argument("--label", required=True)
    variant.add_argument("--description", required=True)
    variant.add_argument("--exposures", type=int)
    variant.add_argument("--successes", type=int)
    variant.add_argument("--share", type=Decimal)
    variant.add_argument("--source", default="MANUAL")
    conclude = sub.add_parser("experiment-conclude")
    conclude.add_argument("experiment_id", type=UUID)
    conclude.add_argument("--conclusion")
    conclude.add_argument("--next", dest="next_experiment")
    sub.add_parser("autopsy").add_argument("content_id", type=UUID)
    for name in ("hooks", "drop-offs", "returning", "validation"):
        sub.add_parser(name)
    sub.add_parser("loop").add_argument("script_id", type=UUID)
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    svc = PerformanceService(engine)
    out: object
    if args.command == "import":
        out = svc.import_studio_csv(
            args.file.read_text(encoding="utf-8"), author=args.author, period=(args.start, args.end)
        )
    elif args.command == "contents":
        out = svc.contents()
    elif args.command == "link":
        svc.link_script(args.content_id, args.script_id, language=args.language)
        out = {"linked": str(args.content_id)}
    elif args.command == "report":
        out = svc.report(min_items=args.min_items)
    elif args.command == "authorize":
        out = _authorize(settings, args.port)
    elif args.command == "sync":
        out = svc.sync_analytics(
            _analytics(settings), args.start, args.end, author=args.author, curves=args.curves
        )
    elif args.command == "objective":
        svc.set_objective(args.content_id, objective=args.objective, format_=args.format)
        out = {"content_id": str(args.content_id), "objective": args.objective}
    elif args.command in ("autopsy", "hooks", "drop-offs", "returning", "validation", "loop"):
        lab = PerformanceLab(engine)
        if args.command == "autopsy":
            out = lab.autopsy(args.content_id)
        elif args.command == "loop":
            out = lab.loop(args.script_id)
        else:
            out = getattr(lab, args.command.replace("-", "_"))()
    elif args.command == "objectives":
        out = svc.objective_report()
    elif args.command == "experiments":
        out = svc.experiments()
    elif args.command == "experiment-create":
        out = {
            "experiment_id": str(
                svc.create_experiment(
                    title=args.title,
                    hypothesis=args.hypothesis,
                    variable=args.variable,
                    metric=args.metric,
                    audience=args.audience,
                    author=args.author,
                )
            )
        }
    elif args.command == "experiment-variant":
        svc.add_variant(
            args.experiment_id,
            label=args.label,
            description=args.description,
            exposures=args.exposures,
            successes=args.successes,
            reported_share=args.share,
            source=args.source,
        )
        out = {"variant": args.label}
    elif args.command == "experiment-conclude":
        out = svc.conclude(
            args.experiment_id, conclusion=args.conclusion, next_experiment=args.next_experiment
        )
    else:
        editorial = editorial_service_from_settings(settings, engine)
        mission_id = editorial.create_mission("PERFORMANCE_REVIEW", [], {})
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
