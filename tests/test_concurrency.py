"""Tests para concurrencia limitada en scraping."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from etl.config import ScrapeConfig
from etl.scrape import ScrapeResult, run_scrape


class _Tracker:
    def __init__(self):
        self.active = 0
        self.peak = 0


@pytest.mark.asyncio
async def test_concurrency_limited():
    import etl.scrape as _s

    original_fetch = _s.fetch_url
    tracker = _Tracker()

    async def fake_fetch(client, url, selectors, rate_limiter, config):
        tracker.active += 1
        tracker.peak = max(tracker.peak, tracker.active)
        await asyncio.sleep(0.05)
        tracker.active -= 1
        return ScrapeResult(url=url, domain="test", data=[{"test": "1"}], status_code=200)

    _s.fetch_url = fake_fetch
    tmpdir = tempfile.mkdtemp()
    tmpdb = str(Path(tmpdir) / "test_concurrency.db")

    try:
        config = ScrapeConfig(max_concurrent=3, db_path=tmpdb)
        await run_scrape(
            [f"http://test{i}.com" for i in range(10)],
            selectors=[".item"],
            config=config,
        )
        assert tracker.peak <= 3, f"Peak concurrency {tracker.peak} > 3"
        assert tracker.peak >= 2, f"Peak concurrency {tracker.peak} < 2 (should parallelize)"
    finally:
        _s.fetch_url = original_fetch
