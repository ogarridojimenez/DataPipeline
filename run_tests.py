"""Tests para ETL core (selectolax + pandas)."""

import json
import sqlite3
import tempfile
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))


def assert_(condition, msg="Assertion failed"):
    if not condition:
        raise AssertionError(msg)


def run_tests():
    import json
    passed = 0
    failed = 0
    errors = []

    # ===== test_scrape.py =====
    print("=" * 60)
    print("test_scrape.py")
    print("=" * 60)

    from etl.scrape import extract_data, RateLimiter

    SAMPLE_HTML = """
    <html><body>
    <div class="products">
        <div class="product">
            <h2 class="title">Laptop Pro</h2>
            <span class="price">$1299</span>
            <span class="stock">In Stock</span>
        </div>
        <div class="product">
            <h2 class="title">Mouse RGB</h2>
            <span class="price">$45</span>
            <span class="stock">Out of Stock</span>
        </div>
        <div class="product">
            <h2 class="title">Teclado Mecánico</h2>
            <span class="price">$89</span>
            <span class="stock">In Stock</span>
        </div>
    </div></body></html>
    """

    scrape_tests = [
        ("extract_single_selector", lambda: (
            (r := extract_data(SAMPLE_HTML, ["h2.title"], "http://test.com", "test.com")),
            assert_(len(r) == 3, f"Expected 3, got {len(r)}"),
            assert_(r[0]["title"] == "Laptop Pro", f"Got {r[0]['title']}"),
        )),
        ("extract_multiple_selectors", lambda: (
            (r := extract_data(SAMPLE_HTML, ["h2.title", ".price", ".stock"], "http://test.com", "test.com")),
            assert_(len(r) == 3, f"Expected 3, got {len(r)}"),
            assert_(r[0]["price"] == "$1299", f"Got price: {r[0].get('price')}"),
            assert_(r[0]["stock"] == "In Stock", f"Got stock: {r[0].get('stock')}"),
        )),
        ("source_metadata", lambda: (
            (r := extract_data(SAMPLE_HTML, ["h2.title"], "http://test.com/products", "test.com")),
            assert_(r[0]["_source_url"] == "http://test.com/products"),
            assert_(r[0]["_source_domain"] == "test.com"),
        )),
        ("empty_html", lambda: (
            (r := extract_data("<html><body></body></html>", ["h2.title"], "http://test.com", "test.com")),
            assert_(r == [], f"Expected [], got {r}"),
        )),
        ("selector_no_match", lambda: (
            (r := extract_data(SAMPLE_HTML, [".nonexistent"], "http://test.com", "test.com")),
            assert_(r == [], f"Expected [], got {r}"),
        )),
        ("mismatched_counts", lambda: (
            (html := '<html><body><h2 class="title">A</h2><h2 class="title">B</h2><span class="price">$10</span></body></html>'),
            (r := extract_data(html, ["h2.title", ".price"], "http://t.com", "t.com")),
            assert_(len(r) == 2, f"Expected 2, got {len(r)}"),
            assert_(r[0]["price"] == "$10"),
            assert_(r[1]["price"] == ""),
        )),
    ]

    for name, test_fn in scrape_tests:
        try:
            test_fn()
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
            errors.append((f"scrape.{name}", e))

    # ===== test_process.py =====
    print()
    print("=" * 60)
    print("test_process.py")
    print("=" * 60)

    import pandas as pd
    from etl.process import load_raw_data, clean_data, save_processed
    from etl.config import ProcessConfig

    def make_test_db(tmpdir):
        import json
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE raw_data (
            id INTEGER PRIMARY KEY, source_url TEXT, source_domain TEXT,
            data TEXT, scraped_at TIMESTAMP
        )""")
        data_items = [
            [{"title": "A", "price": "100"}, {"title": "B", "price": "200"}, {"title": "A", "price": "100"}],
            [{"title": "C", "price": "50"}],
        ]
        for items in data_items:
            conn.execute("INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
                        ("http://test.com", "test.com", json.dumps(items)))
        conn.commit()
        conn.close()
        return db_path

    def _test_fill_nulls(db):
        df = load_raw_data(db)
        df.loc[0, "title"] = ""
        cleaned = clean_data(df, ProcessConfig(fill_null_strategy="fill"))
        assert_(len(cleaned) == 4)

    def _test_drop_nulls(db):
        df = load_raw_data(db)
        df.loc[0, "title"] = None
        cleaned = clean_data(df, ProcessConfig(fill_null_strategy="drop"))
        assert_(len(cleaned) <= 4)

    with tempfile.TemporaryDirectory() as tmpdir:
        db = make_test_db(tmpdir)

        process_tests = [
            ("loads_and_expands_json", lambda: (
                (df := load_raw_data(db)),
                assert_(len(df) == 4, f"Expected 4, got {len(df)}"),
                assert_("title" in df.columns),
            )),
            ("removes_duplicates", lambda: (
                (df := load_raw_data(db)),
                (cleaned := clean_data(df, ProcessConfig(fill_null_strategy="drop"))),
                assert_(len(cleaned) == 3, f"Expected 3, got {len(cleaned)}"),
            )),
            ("fill_nulls_strategy", lambda: _test_fill_nulls(db)),
            ("drop_nulls_strategy", lambda: _test_drop_nulls(db)),
            ("is_dataframe", lambda: assert_(isinstance(load_raw_data(db), pd.DataFrame))),
        ]

        for name, test_fn in process_tests:
            try:
                test_fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
                errors.append((f"process.{name}", e))

        # save_processed test
        try:
            df = load_raw_data(db)
            save_processed(df, db)
            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM processed_data")
            rows = cursor.fetchall()
            conn.close()
            assert_(len(rows) == 4, f"Expected 4, got {len(rows)}")
            print(f"  ✓ save_to_sqlite")
            passed += 1
        except Exception as e:
            print(f"  ✗ save_to_sqlite: {e}")
            failed += 1
            errors.append(("process.save_to_sqlite", e))

    # ===== test_integration.py =====
    print()
    print("=" * 60)
    print("test_integration.py")
    print("=" * 60)

    from etl.export import run_export

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "pipeline.db"
        output_dir = Path(tmpdir) / "output"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_url TEXT,
            source_domain TEXT, data TEXT, scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        items = [
            {"product": "Laptop", "price": "999", "category": "electronics"},
            {"product": "Mouse", "price": "25", "category": "electronics"},
            {"product": "Laptop", "price": "999", "category": "electronics"},
            {"product": "Book", "price": "15", "category": "books"},
            {"product": "", "price": "30", "category": "misc"},
        ]
        conn.execute("INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
                     ("http://test.com/products", "test.com", json.dumps(items)))
        conn.commit()
        conn.close()

        df = load_raw_data(db_path)
        assert_(len(df) == 5, f"Expected 5, got {len(df)}")

        cleaned = clean_data(df, ProcessConfig(fill_null_strategy="drop"))
        save_processed(cleaned, db_path)

        run_export(db_path, ProcessConfig(output_dir=output_dir), fmt="both")

        integration_tests = [
            ("csv_exists", lambda: assert_((output_dir / "datapipeline_export.csv").exists())),
            ("json_exists", lambda: assert_((output_dir / "datapipeline_export.json").exists())),
            ("csv_row_count", lambda: (
                (lines := (output_dir / "datapipeline_export.csv").read_text().strip().split("\n")),
                assert_(len(lines) >= 3, f"Expected >=3 lines, got {len(lines)}"),
            )),
            ("json_row_count", lambda: (
                (data := json.loads((output_dir / "datapipeline_export.json").read_text())),
                assert_(len(data) >= 2, f"Expected >=2, got {len(data)}"),
            )),
        ]

        for name, test_fn in integration_tests:
            try:
                test_fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
                errors.append((f"integration.{name}", e))

        # --- parquet export test ---
        try:
            parquet_path = output_dir / "datapipeline_export.parquet"
            run_export(db_path, ProcessConfig(output_dir=output_dir), fmt="parquet")
            assert_(parquet_path.exists(), f"Parquet file not found: {parquet_path}")
            df_parquet = pd.read_parquet(parquet_path)
            assert_(len(df_parquet) >= 2, f"Expected >=2 rows in parquet, got {len(df_parquet)}")
            print(f"  ✓ parquet_export")
            passed += 1
        except Exception as e:
            print(f"  ✗ parquet_export: {e}")
            failed += 1
            errors.append((f"integration.parquet_export", e))

    # ===== CLI test =====
    print()
    print("=" * 60)
    print("CLI test")
    print("=" * 60)

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "etl", "--help"],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent)
    )
    try:
        assert_(result.returncode == 0, f"Exit code: {result.returncode}")
        assert_("scrape" in result.stdout, "Missing 'scrape' in help")
        assert_("process" in result.stdout, "Missing 'process' in help")
        assert_("export" in result.stdout, "Missing 'export' in help")
        print("  ✓ cli_help")
        passed += 1
    except Exception as e:
        print(f"  ✗ cli_help: {e}")
        failed += 1
        errors.append(("cli.help", e))

    # ===== test_dedup.py =====
    print("=" * 60)
    print("test_dedup.py")
    print("=" * 60)
    try:
        import tempfile as _tf
        _tdb = str(Path(_tf.mkdtemp()) / "test_dedup.db")
        _conn = sqlite3.connect(_tdb)
        _conn.execute("""CREATE TABLE IF NOT EXISTS raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT, source_domain TEXT, data TEXT,
            content_hash TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        _conn.commit()
        _conn.close()
        from etl.scrape import save_to_sqlite, ScrapeResult
        r1 = ScrapeResult(url="http://a.com", domain="a.com", data=[{"x":"1"},{"x":"2"}], status_code=200)
        r2 = ScrapeResult(url="http://a.com", domain="a.com", data=[{"x":"1"},{"x":"2"}], status_code=200)
        r3 = ScrapeResult(url="http://b.com", domain="b.com", data=[{"x":"3"},{"x":"4"}], status_code=200)
        n1, _ = save_to_sqlite([r1, r2, r3], _tdb, incremental=True)
        assert_(n1 == 4, f"Expected 4 items (r1=2 skip dup, r3=2), got {n1}")
        _c1 = sqlite3.connect(_tdb).execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
        assert_(_c1 == 2, f"Expected 2 rows (no hash UNIQUE, dedup by SELECT), got {_c1}")
        n2, _ = save_to_sqlite([r1], _tdb, incremental=True)
        assert_(n2 == 0, f"Expected 0 new on repeat, got {n2}")
        n3, _ = save_to_sqlite([r1], _tdb, incremental=False)
        assert_(n3 == 2, f"Expected 2 items with no-incremental, got {n3}")
        passed += 1
        print(f"  ✓ incremental_dedup_works")
    except Exception as e:
        print(f"  ✗ incremental_dedup_works: {e}")
        failed += 1
        errors.append(("dedup_test", e))

    # ===== test_notify.py =====
    print("=" * 60)
    print("test_notify.py")
    print("=" * 60)
    try:
        import http.server
        import threading
        import json
        from etl.notify import send_webhook, notify_scrape_complete

        _received: list[dict] = []

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                _received.append(json.loads(body))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        _server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        _port = _server.server_port
        _t = threading.Thread(target=_server.handle_request, daemon=True)
        _t.start()

        _ok = send_webhook(f"http://127.0.0.1:{_port}", "test msg", {"key": "val"})
        _t.join(timeout=3)
        assert_(_ok, "send_webhook should return True")
        assert_(len(_received) == 1, f"Expected 1 request, got {len(_received)}")
        assert_(_received[0]["text"] == "test msg", f"Wrong text: {_received[0]}")
        passed += 1
        print(f"  ✓ webhook_send")
    except Exception as e:
        print(f"  ✗ webhook_send: {e}")
        failed += 1
        errors.append(("notify_test", e))

    # ===== test_advanced_pandas.py =====
    print("=" * 60)
    print("test_advanced_pandas.py")
    print("=" * 60)
    try:
        import pandas as _pd
        from etl.process import compute_summary, group_by_domain, pipeline_pipe
        _df = _pd.DataFrame({
            "_source_domain": ["a.com","a.com","b.com","b.com"],
            "value": [10, 20, 30, 40],
            "category": ["x","y","x","y"],
        })
        _s = compute_summary(_df)
        assert_(_s["total_records"] == 4, f"summary count: {_s}")
        assert_(_s["numeric_columns"] == 1, f"numeric cols: {_s}")
        assert_("a.com" in _s["top_domains"], f"top_domains: {_s}")
        passed += 1
        print(f"  ✓ compute_summary")
        _gb = group_by_domain(_df)
        assert_(len(_gb) == 2, f"group_by should have 2 domains, got {len(_gb)}")
        assert_("value_mean" in _gb.columns, f"column value_mean missing: {_gb.columns.tolist()}")
        passed += 1
        print(f"  ✓ group_by_domain")
        _filtered = pipeline_pipe(_df, [{"type": "filter", "params": {"column": "value", "op": "gt", "value": 20}}])
        assert_(len(_filtered) == 2, f"filter >20 expected 2, got {len(_filtered)}")
        passed += 1
        print(f"  ✓ pipeline_pipe_filter")
        _ranked = pipeline_pipe(_df, [{"type": "add_rank", "params": {"column": "value", "name": "r"}}])
        assert_("r" in _ranked.columns, f"rank column missing")
        passed += 1
        print(f"  ✓ pipeline_pipe_rank")
    except Exception as e:
        print(f"  ✗ advanced_pandas: {e}")
        failed += 1
        errors.append(("advanced_pandas", e))

    # ===== test_concurrency.py =====
    print("=" * 60)
    print("test_concurrency.py")
    print("=" * 60)
    from etl.scrape import run_scrape, ScrapeResult
    from etl.config import ScrapeConfig

    class _Tracker:
        def __init__(self):
            self.active = 0
            self.peak = 0

    async def _test_concurrency_limits():
        tracker = _Tracker()
        import etl.scrape as _s
        original_fetch = _s.fetch_url

        async def fake_fetch(client, url, selectors, rate_limiter, config):
            tracker.active += 1
            tracker.peak = max(tracker.peak, tracker.active)
            await asyncio.sleep(0.05)
            tracker.active -= 1
            return ScrapeResult(url=url, domain="test", data=[{"test": "1"}], status_code=200)

        _s.fetch_url = fake_fetch
        import tempfile
        _tmpdir = tempfile.mkdtemp()
        tmpdb = str(Path(_tmpdir) / "test_concurrency.db")
        config = ScrapeConfig(max_concurrent=3, db_path=tmpdb)
        await run_scrape(
            [f"http://test{i}.com" for i in range(10)],
            selectors=[".item"],
            config=config,
        )
        _s.fetch_url = original_fetch
        return tracker.peak

    try:
        peak = asyncio.run(_test_concurrency_limits())
        assert_(peak <= 3, f"Concurrency peak {peak} > 3")
        assert_(peak >= 2, f"Concurrency peak {peak} < 2 (should have at least some parallelism)")
        passed += 1
        print(f"  ✓ concurrency_limited (peak={peak})")
    except Exception as e:
        print(f"  ✗ concurrency_limited: {e}")
        failed += 1
        errors.append(("concurrency_test", e))

    # ===== Summary =====
    print()
    print("=" * 60)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
