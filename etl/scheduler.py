"""Programador automático de pipelines ETL.

Crea tareas programadas en el sistema (cron en Linux, schtasks en Windows).

Uso:
    python -m etl schedule --cron "0 */6 * * *"
    python -m etl schedule --list
    python -m etl schedule --remove
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def _schedule_path() -> Path:
    """Retorna ruta del archivo de configuración de schedule."""
    return Path("data/schedule.json")


def save_schedule(cron_expr: str, urls: list[str], selectors: list[str], db_path: str) -> None:
    """Guarda la configuración del schedule en un archivo JSON."""
    schedule_dir = _schedule_path().parent
    schedule_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "cron": cron_expr,
        "urls": urls,
        "selectors": selectors,
        "db_path": db_path,
    }
    _schedule_path().write_text(json.dumps(data, indent=2))
    print(f"✓ Schedule guardado: {_schedule_path()}")


def load_schedule() -> dict | None:
    """Carga la configuración del schedule desde JSON. Retorna None si no existe."""
    path = _schedule_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


def install_task(cron_expr: str, command: str | None = None) -> None:
    """Instala una tarea programada en el sistema.

    En Windows usa schtasks.exe (Task Scheduler).
    En Linux añade entrada al crontab.
    """
    if sys.platform == "win32":
        _install_windows(cron_expr, command)
    else:
        _install_unix(cron_expr, command)


def _install_windows(cron_expr: str, command: str | None = None) -> None:
    """Instala tarea en Windows Task Scheduler."""
    # Convertir cron a minutos/hora/día semanal de schtasks
    parts = cron_expr.split()
    if len(parts) != 5:
        print(f"⚠ Expresión cron inválida: {cron_expr}")
        return

    minute, hour, _, _, day_week = parts

    # Crear script .bat temporal
    python_exe = sys.executable
    task_name = "DataPipelineETL"
    if command is None:
        command = f'"{python_exe}" -m etl run'

    # Crear archivo .bat
    bat_dir = Path(tempfile.gettempdir()) / "datapipeline"
    bat_dir.mkdir(parents=True, exist_ok=True)
    bat_path = bat_dir / "run_etl.bat"
    bat_path.write_text(f'@echo off\ncd /d "{os.getcwd()}"\n{command}\n')

    # Construir comando schtasks
    schtasks_cmd = [
        "schtasks.exe",
        "/Create",
        "/SC",
        "WEEKLY" if day_week != "*" else "DAILY",
        "/TN",
        task_name,
        "/TR",
        str(bat_path),
        "/F",
    ]

    if minute != "*":
        schtasks_cmd.extend(["/MO", minute])
    if hour != "*":
        schtasks_cmd.extend(["/ST", f"{hour.zfill(2)}:{minute.zfill(2)}"])
    if day_week != "*":
        schtasks_cmd.extend(["/D", day_week.upper()])

    import subprocess

    result = subprocess.run(schtasks_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Tarea '{task_name}' creada en Task Scheduler (cron: {cron_expr})")
    else:
        print(f"⚠ Error creando tarea: {result.stderr.strip()}")


def _install_unix(cron_expr: str, command: str | None = None) -> None:
    """Instala tarea via crontab en Linux/macOS."""
    python_exe = sys.executable
    if command is None:
        command = f"cd {os.getcwd()} && {python_exe} -m etl run"

    # Leer crontab actual
    import subprocess

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    # Filtrar entradas previas de DataPipeline
    lines = [ln for ln in existing.splitlines() if "DataPipeline" not in ln]
    lines.append("# DataPipeline schedule")
    lines.append(f"{cron_expr} {command}")

    # Escribir nuevo crontab
    new_cron = "\n".join(lines) + "\n"
    proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    proc.communicate(new_cron)
    print(f"✓ Tarea creada en crontab (cron: {cron_expr})")


def remove_task() -> None:
    """Elimina la tarea programada del sistema."""
    if sys.platform == "win32":
        import subprocess

        result = subprocess.run(
            ["schtasks.exe", "/Delete", "/TN", "DataPipelineETL", "/F"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("✓ Tarea eliminada de Task Scheduler")
        else:
            print("⚠ No se encontró tarea 'DataPipelineETL'")
    else:
        import subprocess

        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = [ln for ln in result.stdout.splitlines() if "DataPipeline" not in ln]
            new_cron = "\n".join(lines) + "\n"
            proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
            proc.communicate(new_cron)
            print("✓ Tarea eliminada de crontab")

    # Limpiar archivo schedule
    path = _schedule_path()
    if path.exists():
        path.unlink()
