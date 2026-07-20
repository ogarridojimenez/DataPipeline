"""Tests para dedup incremental por hash SHA256."""

import sqlite3
import tempfile
from pathlib import Path

from etl.scrape import ScrapeResult, save_to_sqlite


def _make_db():
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test_dedup.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE IF NOT EXISTS raw_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url TEXT, source_domain TEXT, data TEXT,
        content_hash TEXT,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()
    return db_path


class TestIncrementalDedup:
    def test_incremental_skips_duplicates(self):
        db = _make_db()
        r1 = ScrapeResult(url="http://a.com", domain="a.com", data=[{"x": "1"}, {"x": "2"}], status_code=200)
        r2 = ScrapeResult(url="http://a.com", domain="a.com", data=[{"x": "1"}, {"x": "2"}], status_code=200)
        r3 = ScrapeResult(url="http://b.com", domain="b.com", data=[{"x": "3"}, {"x": "4"}], status_code=200)
        n1, _ = save_to_sqlite([r1, r2, r3], db, incremental=True)
        assert n1 == 4
        count = sqlite3.connect(str(db)).execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
        assert count == 2

    def test_repeat_returns_zero(self):
        db = _make_db()
        r1 = ScrapeResult(url="http://a.com", domain="a.com", data=[{"x": "1"}], status_code=200)
        save_to_sqlite([r1], db, incremental=True)
        n, _ = save_to_sqlite([r1], db, incremental=True)
        assert n == 0

    def test_no_incremental_inserts_all(self):
        db = _make_db()
        r1 = ScrapeResult(url="http://a.com", domain="a.com", data=[{"x": "1"}], status_code=200)
        n, _ = save_to_sqlite([r1], db, incremental=False)
        assert n == 1
