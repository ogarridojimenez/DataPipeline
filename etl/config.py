"""Configuración central del pipeline ETL."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# User-Agents para rotación
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
]


@dataclass
class ScrapeConfig:
    """Configuración para la fase de scraping."""
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 1.0  # segundos entre requests por dominio
    db_path: Path = field(default_factory=lambda: Path("data/pipeline.db"))
    user_agents: list[str] = field(default_factory=lambda: USER_AGENTS.copy())


@dataclass
class ProcessConfig:
    """Configuración para la fase de procesamiento."""
    outlier_std_threshold: float = 3.0
    fill_null_strategy: str = "drop"  # drop | fill | mean | median
    output_dir: Path = field(default_factory=lambda: Path("data/processed"))


def get_scrape_config(**overrides) -> ScrapeConfig:
    """Crea ScrapeConfig con overrides de env vars y kwargs."""
    defaults = ScrapeConfig()
    defaults.db_path = Path(os.getenv("ETL_DB_PATH", str(defaults.db_path)))
    defaults.timeout = int(os.getenv("ETL_TIMEOUT", str(defaults.timeout)))
    defaults.rate_limit_delay = float(os.getenv("ETL_RATE_LIMIT", str(defaults.rate_limit_delay)))
    for k, v in overrides.items():
        if v is not None:
            setattr(defaults, k, v)
    return defaults


def get_process_config(**overrides) -> ProcessConfig:
    """Crea ProcessConfig con overrides de env vars y kwargs."""
    defaults = ProcessConfig()
    defaults.output_dir = Path(os.getenv("ETL_OUTPUT_DIR", str(defaults.output_dir)))
    for k, v in overrides.items():
        if v is not None:
            setattr(defaults, k, v)
    return defaults
