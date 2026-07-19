"""CLI principal: python -m etl [scrape|process|export] [--help]"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="etl",
        description="Pipeline ETL: scraping → procesamiento → exportación",
    )
    sub = parser.add_subparsers(dest="command", help="Subcomandos disponibles")

    # --- scrape ---
    sp = sub.add_parser("scrape", help="Extraer datos de URLs via scraping")
    sp.add_argument("urls", nargs="+", help="URLs a scrapear")
    sp.add_argument(
        "--selectors", nargs="+", required=True,
        help="CSS selectors para extraer datos (ej: \"h2.title\" \".price\")",
    )
    sp.add_argument("--timeout", type=int, default=30, help="Timeout por request (s)")
    sp.add_argument("--rate-limit", type=float, default=1.0, help="Delay entre requests (s)")
    sp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")

    # --- process ---
    pp = sub.add_parser("process", help="Limpiar y transformar datos")
    pp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    pp.add_argument("--outlier-threshold", type=float, default=3.0, help="Umbrales std-dev para outliers")
    pp.add_argument("--fill-nulls", choices=["drop", "fill", "mean", "median"], default="drop")

    # --- export ---
    ep = sub.add_parser("export", help="Exportar datos procesados a CSV/JSON")
    ep.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    ep.add_argument("--output-dir", type=str, default="data/processed", help="Directorio de salida")
    ep.add_argument("--format", choices=["csv", "json", "both"], default="both")

    # --- dashboard ---
    dp = sub.add_parser("dashboard", help="Abrir dashboard web interactivo")
    dp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    dp.add_argument("--port", type=int, default=8501, help="Puerto del servidor")
    dp.add_argument("--host", type=str, default="127.0.0.1", help="Host del servidor")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "scrape":
        from etl.scrape import run_scrape
        from etl.config import ScrapeConfig

        config = ScrapeConfig(
            timeout=args.timeout,
            rate_limit_delay=args.rate_limit,
            db_path=Path(args.db),
        )
        asyncio.run(run_scrape(args.urls, args.selectors, config))

    elif args.command == "process":
        from etl.process import run_process
        from etl.config import ProcessConfig

        config = ProcessConfig(
            outlier_std_threshold=args.outlier_threshold,
            fill_null_strategy=args.fill_nulls,
        )
        run_process(Path(args.db), config)

    elif args.command == "export":
        from etl.export import run_export
        from etl.config import ProcessConfig

        config = ProcessConfig(output_dir=Path(args.output_dir))
        run_export(Path(args.db), config, fmt=args.format)

    elif args.command == "dashboard":
        import uvicorn
        from dashboard.app import app

        # Override DB_PATH
        from dashboard import app as dash_app
        from pathlib import Path as _P
        dash_app.DB_PATH = _P(args.db)

        print(f"🌐 Dashboard: http://{args.host}:{args.port}")
        uvicorn.run(dash_app.app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
