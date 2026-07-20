"""CLI principal: python -m etl [scrape|process|export|run|dashboard|schedule|cleanup] [--help]"""

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
        "--selectors",
        nargs="+",
        required=True,
        help='CSS selectors para extraer datos (ej: "h2.title" ".price")',
    )
    sp.add_argument("--timeout", type=int, default=30, help="Timeout por request (s)")
    sp.add_argument("--rate-limit", type=float, default=1.0, help="Delay entre requests (s)")
    sp.add_argument("--concurrency", type=int, default=10, help="Máximo requests simultáneos")
    sp.add_argument(
        "--incremental/--no-incremental",
        dest="incremental",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Evitar duplicados por hash",
    )
    sp.add_argument("--webhook", type=str, default=None, help="URL de webhook (o variable ETL_WEBHOOK_URL)")
    sp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")

    # --- process ---
    pp = sub.add_parser("process", help="Limpiar y transformar datos")
    pp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    pp.add_argument("--outlier-threshold", type=float, default=3.0, help="Umbral std-dev para outliers")
    pp.add_argument("--fill-nulls", choices=["drop", "fill", "mean", "median"], default="drop")

    # --- export ---
    ep = sub.add_parser("export", help="Exportar datos procesados a CSV/JSON")
    ep.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    ep.add_argument("--output-dir", type=str, default="data/processed", help="Directorio de salida")
    ep.add_argument("--format", choices=["csv", "json", "both", "parquet"], default="both")
    ep.add_argument("--since", type=str, default=None, help='Exportar solo registros >= fecha ISO (ej: "2026-07-01")')

    # --- dashboard ---
    dp = sub.add_parser("dashboard", help="Abrir dashboard web interactivo")
    dp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    dp.add_argument("--port", type=int, default=8501, help="Puerto del servidor")
    dp.add_argument("--host", type=str, default="127.0.0.1", help="Host del servidor")
    dp.add_argument(
        "--mode",
        choices=["starlette", "streamlit"],
        default="streamlit",
        help="Motor del dashboard (starlette=HTML+Chart.js, streamlit=Streamlit+Plotly)",
    )

    # --- run (batch) ---
    rp = sub.add_parser("run", help="Pipeline batch completo: scrape → process → export → notify")
    rp.add_argument("urls", nargs="+", help="URLs a scrapear")
    rp.add_argument("--selectors", nargs="+", required=True, help='CSS selectors (ej: "h2.title" ".price")')
    rp.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")
    rp.add_argument("--output-dir", type=str, default="data/processed", help="Directorio de salida")
    rp.add_argument(
        "--format", choices=["csv", "json", "both", "parquet"], default="both", help="Formato de exportación"
    )
    rp.add_argument("--webhook", type=str, default=None, help="URL de webhook (o variable ETL_WEBHOOK_URL)")
    rp.add_argument("--timeout", type=int, default=30, help="Timeout por request (s)")
    rp.add_argument("--rate-limit", type=float, default=1.0, help="Delay entre requests (s)")
    rp.add_argument("--concurrency", type=int, default=10, help="Máximo requests simultáneos")
    rp.add_argument(
        "--no-incremental", dest="incremental", action="store_false", default=True, help="No evitar duplicados"
    )
    rp.add_argument("--outlier-threshold", type=float, default=3.0, help="Umbral std-dev para outliers")
    rp.add_argument("--fill-nulls", choices=["drop", "fill", "mean", "median"], default="drop")

    # --- cleanup ---
    cl = sub.add_parser("cleanup", help="Purgar datos antiguos")
    cl.add_argument("--days", type=int, default=30, help="Registros más antiguos que N días")
    cl.add_argument("--dry-run", action="store_true", help="Solo contar sin eliminar")
    cl.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")

    # --- schedule ---
    sp_cmd = sub.add_parser("schedule", help="Gestionar tareas programadas")
    sp_cmd.add_argument("--cron", type=str, default=None, help='Expresión cron (ej: "0 */6 * * *")')
    sp_cmd.add_argument("--list", action="store_true", help="Listar tareas programadas")
    sp_cmd.add_argument("--remove", action="store_true", help="Eliminar tarea programada")
    sp_cmd.add_argument("--urls", nargs="+", default=None, help="URLs a scrapear (para schedule)")
    sp_cmd.add_argument("--selectors", nargs="+", default=None, help="CSS selectors (para schedule)")

    # --- api ---
    ap = sub.add_parser("api", help="Iniciar servidor REST API")
    ap.add_argument("--host", type=str, default="127.0.0.1", help="Host")
    ap.add_argument("--port", type=int, default=8000, help="Puerto")
    ap.add_argument("--db", type=str, default="data/pipeline.db", help="Ruta SQLite")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "scrape":
        from etl.config import get_scrape_config
        from etl.scrape import run_scrape

        config = get_scrape_config(
            timeout=args.timeout,
            rate_limit_delay=args.rate_limit,
            db_path=Path(args.db),
            max_concurrent=args.concurrency,
            incremental=args.incremental,
            webhook_url=args.webhook,
        )
        asyncio.run(run_scrape(args.urls, args.selectors, config))

    elif args.command == "process":
        from etl.config import ProcessConfig
        from etl.process import run_process

        config = ProcessConfig(
            outlier_std_threshold=args.outlier_threshold,
            fill_null_strategy=args.fill_nulls,
        )
        run_process(Path(args.db), config)

    elif args.command == "export":
        from etl.config import ProcessConfig
        from etl.export import run_export

        config = ProcessConfig(output_dir=Path(args.output_dir))
        run_export(db_path=Path(args.db), config=config, fmt=args.format, since=args.since)

    elif args.command == "dashboard":
        if args.mode == "streamlit":
            import os
            import subprocess

            env = os.environ.copy()
            env["ETL_DB_PATH"] = args.db
            app_path = str(Path(__file__).parent.parent / "dashboard" / "streamlit_app.py")
            print(f"🌐 Dashboard Streamlit: http://{args.host}:{args.port}")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    app_path,
                    "--server.port",
                    str(args.port),
                    "--server.address",
                    args.host,
                ],
                env=env,
            )
        else:
            import uvicorn

            from dashboard import app as dash_app

            dash_app.DB_PATH = Path(args.db)

            print(f"🌐 Dashboard Starlette: http://{args.host}:{args.port}")
            uvicorn.run(dash_app.app, host=args.host, port=args.port)

    elif args.command == "run":
        from etl.config import get_process_config, get_scrape_config
        from etl.export import run_export
        from etl.notify import notify_scrape_complete
        from etl.process import run_process
        from etl.scrape import run_scrape

        db_path = Path(args.db)
        output_dir = Path(args.output_dir)

        # 1. Scrape
        scrape_cfg = get_scrape_config(
            timeout=args.timeout,
            rate_limit_delay=args.rate_limit,
            db_path=db_path,
            max_concurrent=args.concurrency,
            incremental=args.incremental,
            webhook_url=args.webhook,
        )
        total_rows = asyncio.run(run_scrape(args.urls, args.selectors, scrape_cfg))
        if total_rows == 0:
            print("⚠ No se extrajeron datos. Pipeline detenido.")
            return

        # 2. Process
        process_cfg = get_process_config(
            outlier_std_threshold=args.outlier_threshold,
            fill_null_strategy=args.fill_nulls,
            output_dir=output_dir,
        )
        run_process(db_path, process_cfg)

        # 3. Export
        run_export(db_path=db_path, config=process_cfg, fmt=args.format)

        # 4. Notify
        if args.webhook:
            notify_scrape_complete(
                webhook_url=args.webhook,
                status="success",
                total_rows=total_rows,
                num_sources=len(args.urls),
                selectors=args.selectors,
            )

        print(f"✅ Pipeline batch completo ({total_rows} filas)")

    elif args.command == "schedule":
        from etl.scheduler import (
            install_task,
            load_schedule,
            remove_task,
            save_schedule,
        )

        if args.remove:
            remove_task()
        elif args.cron:
            save_schedule(
                cron_expr=args.cron,
                urls=args.urls or [],
                selectors=args.selectors or [],
                db_path=args.db if hasattr(args, "db") else "data/pipeline.db",
            )
            install_task(args.cron)
        elif args.list:
            sched = load_schedule()
            if sched:
                print(f"Cron:  {sched['cron']}")
                print(f"URLs:  {', '.join(sched.get('urls', []))}")
                print(f"DB:    {sched.get('db_path', 'data/pipeline.db')}")
            else:
                print("No hay tareas programadas.")
        else:
            sched = load_schedule()
            if sched:
                install_task(sched["cron"])
            else:
                print("No hay schedule guardado. Usa --cron para crear uno.")

    elif args.command == "cleanup":
        from etl.cleanup import cleanup_db

        counts = cleanup_db(
            db_path=Path(args.db),
            days=args.days,
            dry_run=args.dry_run,
        )
        total = counts.get("raw_data", 0) + counts.get("processed_data", 0)
        if total == 0 and not args.dry_run:
            print("✓ No hay datos antiguos que purgar.")
        print(f"  Total: {total} registros {'(simulado)' if args.dry_run else 'eliminados'}")

    elif args.command == "api":
        from dashboard.api import serve

        serve(host=args.host, port=args.port, db_path=args.db)


if __name__ == "__main__":
    main()
