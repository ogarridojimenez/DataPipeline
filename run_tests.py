"""Tests para ETL core (selectolax + pandas)."""

import json
import sqlite3
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))


def assert_(condition, msg="Assertion failed"):
    if not condition:
        raise AssertionError(msg)


def run_tests():
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
