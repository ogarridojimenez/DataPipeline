"""Fase de extracción: httpx async + selectolax + rate limit + retry."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import sqlite3
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

from etl.config import ScrapeConfig

logger = logging.getLogger("etl.scrape")


@dataclass
class ScrapeResult:
    """Resultado de scraping de una URL."""

    url: str
    domain: str
    data: list[dict[str, str]]
    status_code: int
    error: str | None = None


class RateLimiter:
    """Rate limit por dominio."""

    def __init__(self, delay: float = 1.0):
        self._delay = delay
        self._last_request: dict[str, float] = {}

    async def wait(self, domain: str) -> None:
        now = asyncio.get_event_loop().time()
        last = self._last_request.get(domain, 0)
        wait_time = max(0, self._delay - (now - last))
        if wait_time > 0:
            logger.debug("Rate limit: waiting %.1fs for %s", wait_time, domain)
            await asyncio.sleep(wait_time)
        self._last_request[domain] = asyncio.get_event_loop().time()


def extract_data(html_content: str, selectors: list[str], url: str, domain: str) -> list[dict[str, str]]:
    """Extrae datos del HTML usando selectolax CSS selectors."""
    tree = HTMLParser(html_content)
    if not tree.root:
        return []

    results: list[dict[str, str]] = []

    # Encontrar matches por selector
    all_matches = []
    for sel in selectors:
        matches = tree.css(sel)
        all_matches.append(matches if matches else [])

    max_len = max((len(m) for m in all_matches), default=0)

    for i in range(max_len):
        row: dict[str, str] = {"_source_url": url, "_source_domain": domain}
        for sel, matches in zip(selectors, all_matches):
            # Limpiar selector para usar como key
            clean_sel = sel.strip().lstrip(".#").split("[")[0]
            if "." in clean_sel:
                clean_sel = clean_sel.split(".")[-1]

            if i < len(matches):
                node = matches[i]
                row[clean_sel] = node.text(strip=True)
            else:
                row[clean_sel] = ""
        results.append(row)

    return results


async def fetch_url(
    client: httpx.AsyncClient,
    url: str,
    selectors: list[str],
    rate_limiter: RateLimiter,
    config: ScrapeConfig,
) -> ScrapeResult:
    """Descarga y procesa una URL individual con retry."""
    domain = urlparse(url).netloc
    user_agent = random.choice(config.user_agents)

    for attempt in range(config.max_retries):
        try:
            await rate_limiter.wait(domain)
            logger.info("Fetching %s (attempt %d/%d)", url, attempt + 1, config.max_retries)

            response = await client.get(
                url,
                headers={"User-Agent": user_agent},
                timeout=config.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()

            data = extract_data(response.text, selectors, url, domain)
            logger.info("Extracted %d items from %s", len(data), url)

            return ScrapeResult(
                url=url,
                domain=domain,
                data=data,
                status_code=response.status_code,
            )

        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d for %s (attempt %d)", e.response.status_code, url, attempt + 1)
            if attempt == config.max_retries - 1:
                return ScrapeResult(url=url, domain=domain, data=[], status_code=e.response.status_code, error=str(e))
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("Connection error for %s: %s (attempt %d)", url, e, attempt + 1)
            if attempt == config.max_retries - 1:
                return ScrapeResult(url=url, domain=domain, data=[], status_code=0, error=str(e))
            await asyncio.sleep(2**attempt)

    return ScrapeResult(url=url, domain=domain, data=[], status_code=0, error="Max retries exceeded")


def save_to_sqlite(results: list[ScrapeResult], db_path, incremental: bool = True) -> int:
    """Guarda resultados en SQLite. Retorna total de filas insertadas."""
    import hashlib
    from pathlib import Path

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            source_domain TEXT,
            data TEXT,
            content_hash TEXT UNIQUE,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    skipped = 0
    total_rows = 0
    for result in results:
        if not result.data:
            continue
        payload = json.dumps(result.data, sort_keys=True)
        hash_input = f"{result.url}:{payload}".encode()
        content_hash = hashlib.sha256(hash_input).hexdigest()

        if incremental:
            cursor.execute("SELECT 1 FROM raw_data WHERE content_hash = ?", (content_hash,))
            if cursor.fetchone():
                skipped += len(result.data)
                continue

        cursor.execute(
            "INSERT OR IGNORE INTO raw_data (source_url, source_domain, data, content_hash) VALUES (?, ?, ?, ?)",
            (result.url, result.domain, payload, content_hash),
        )
        total_rows += len(result.data)

    conn.commit()
    conn.close()
    if incremental and skipped:
        logger.info("  ↻ Saltados por duplicado: %s filas", skipped)
    return total_rows, skipped


async def run_scrape(urls: list[str], selectors: list[str], config: ScrapeConfig) -> None:
    """Ejecuta el pipeline de scraping completo con concurrencia limitada."""
    rate_limiter = RateLimiter(config.rate_limit_delay)
    semaphore = asyncio.Semaphore(config.max_concurrent)

    async def fetch_with_limit(url: str) -> ScrapeResult:
        async with semaphore:
            transport = httpx.AsyncHTTPTransport(retries=config.max_retries)
            async with httpx.AsyncClient(transport=transport) as client:
                return await fetch_url(client, url, selectors, rate_limiter, config)

    tasks = [fetch_with_limit(url) for url in urls]
    results = await asyncio.gather(*tasks)

    total, skipped = save_to_sqlite(results, config.db_path, incremental=config.incremental)

    success = sum(1 for r in results if not r.error)
    failed = len(results) - success
    logger.info(
        "✓ Scraping completo: %s/%s URLs, %s filas guardadas en %s", success, len(results), total, config.db_path
    )
    if failed:
        logger.warning("✗ %s URLs fallaron", failed)
        for r in results:
            if r.error:
                logger.warning("  - %s: %s", r.url, r.error)

    # Webhook notification
    if config.webhook_url:
        from etl.notify import notify_scrape_complete

        notify_scrape_complete(
            config.webhook_url,
            total_urls=len(results),
            success_count=success,
            total_rows=total,
            skipped=skipped,
            db_path=str(config.db_path),
        )
