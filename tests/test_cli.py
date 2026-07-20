"""Tests para CLI (argparse)."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


class TestCliHelp:
    def test_main_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "etl", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "scrape" in result.stdout
        assert "process" in result.stdout
        assert "export" in result.stdout
        assert "dashboard" in result.stdout

    def test_scrape_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "etl", "scrape", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "--selectors" in result.stdout
        assert "--webhook" in result.stdout

    def test_dashboard_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "etl", "dashboard", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "streamlit" in result.stdout
        assert "starlette" in result.stdout
