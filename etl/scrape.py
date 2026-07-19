"""Fase de extracción: httpx async + lxml XPath + rate limit + retry."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from lxml import etree

from etl.config import ScrapeConfig

logger = logging.getLogger("etl.scrape")


def _css_to_xpath(selector: str) -> str:
    """Convierte selectores CSS simples a XPath.

    Soporta: h2.title, .title, h2, #id, div > span, tag[attr="val"]
    """
    sel = selector.strip()

    # ID selector: #myid
    if sel.startswith("#"):
        return f'//*[@id="{sel[1:]}"]'

    # Class-only selector: .classname
    if sel.startswith(".") and " " not in sel:
        return f'//*[contains(concat(" ",normalize-space(@class)," "),concat(" ","{sel[1:]}"," "))]'

    # Tag with class: h2.classname
    m = re.match(r'^(\w+)\.([\w-]+)$', sel)
    if m:
        tag, cls = m.groups()
        return f'//{tag}[contains(concat(" ",normalize-space(@class)," "),concat(" ","{cls}"," "))]'

    # Tag with attribute: tag[attr="val"]
    m = re.match(r'^(\w+)\[(\w+)="([^"]+)"\]$', sel)
    if m:
        tag, attr, val = m.groups()
        return f'//{tag}[@{attr}="{val}"]'

    # Descendant: parent > child or parent child
    if ">" in sel:
        parts = [p.strip() for p in sel.split(">")]
        xpath = "//" + "/".join(parts)
        return xpath

    # Space-separated descendants
    if " " in sel:
        parts = sel.split()
        xpath = "//" + "/".join(parts)
        return xpath

    # Simple tag: h2, div, span
    if re.match(r'^[\w]+$', sel):
        return f"//{sel}"

    # Fallback: contains class
    return f'//*[contains(concat(" ",normalize-space(@class)," "),concat(" ","{sel}"," "))]'


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
    """Extrae datos del HTML usando CSS selectors (convertidos a XPath)."""
    tree = etree.HTML(html_content)
    if tree is None:
        return []

    results: list[dict[str, str]] = []

    # Encontrar el número máximo de elementos entre todos los selectors
    all_matches = []
    for sel in selectors:
        try:
            xpath = _css_to_xpath(sel)
            matches = tree.xpath(xpath)
        except Exception as e:
            logger.warning("Selector '%s' falló: %s", sel, e)
            matches = []
        all_matches.append(matches)

    max_len = max((len(m) for m in all_matches), default=0)

    for i in range(max_len):
        row: dict[str, str] = {"_source_url": url, "_source_domain": domain}
        for sel, matches in zip(selectors, all_matches):
            # Extraer nombre descriptivo del selector para la key
            raw = sel.strip().lstrip(".#").split("[")[0]
            if "." in raw:
                # h2.title → "title" (la parte del class es más descriptiva)
                clean_sel = raw.split(".")[-1]
            else:
                clean_sel = raw
            if i < len(matches):
                el = matches[i]
                text = etree.tostring(el, method="text", encoding="unicode").strip()
                row[clean_sel] = text
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
            await asyncio.sleep(2 ** attempt)  # backoff exponencial

    return ScrapeResult(url=url, domain=domain, data=[], status_code=0, error="Max retries exceeded")


def save_to_sqlite(results: list[ScrapeResult], db_path) -> int:
    """Guarda resultados en SQLite. Retorna total de filas insertadas."""
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
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    total_rows = 0
    for result in results:
        if result.data:
            cursor.execute(
                "INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
                (result.url, result.domain, json.dumps(result.data)),
            )
            total_rows += len(result.data)

    conn.commit()
    conn.close()
    return total_rows


async def run_scrape(urls: list[str], selectors: list[str], config: ScrapeConfig) -> None:
    """Ejecuta el pipeline de scraping completo."""
    rate_limiter = RateLimiter(config.rate_limit_delay)
    results: list[ScrapeResult] = []

    transport = httpx.AsyncHTTPTransport(retries=config.max_retries)
    async with httpx.AsyncClient(transport=transport) as client:
        tasks = [fetch_url(client, url, selectors, rate_limiter, config) for url in urls]
        results = await asyncio.gather(*tasks)

    total = save_to_sqlite(results, config.db_path)

    success = sum(1 for r in results if not r.error)
    failed = len(results) - success
    print(f"✓ Scraping completo: {success}/{len(results)} URLs, {total} filas guardadas en {config.db_path}")
    if failed:
        print(f"✗ {failed} URLs fallaron")
        for r in results:
            if r.error:
                print(f"  - {r.url}: {r.error}")
