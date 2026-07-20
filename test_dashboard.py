"""Tests para el dashboard (Starlette + queries)."""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def assert_(condition, msg="Assertion failed"):
    if not condition:
        raise AssertionError(msg)


def make_test_db(tmpdir):
    db_path = Path(tmpdir) / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE processed_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_url TEXT,
        source_domain TEXT, data TEXT, scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    items = [
        ("http://a.com/1", "a.com", {"title": "Item A", "price": "100"}),
        ("http://a.com/2", "a.com", {"title": "Item B", "price": "200"}),
        ("http://b.com/1", "b.com", {"title": "Item C", "price": "50"}),
    ]
    for url, domain, data in items:
        conn.execute(
            "INSERT INTO processed_data (source_url, source_domain, data) VALUES (?, ?, ?)",
            (url, domain, json.dumps(data)),
        )
    conn.commit()
    conn.close()
    return db_path


def run_tests():
    passed = 0
    failed = 0
    errors = []

    print("=" * 60)
    print("test_dashboard_queries.py")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        db = make_test_db(tmpdir)

        from dashboard.queries import (
            get_column_names,
            get_domain_breakdown,
            get_records,
            get_stats,
            get_time_series,
            get_top_items,
        )

        query_tests = [
            ("stats_total", lambda: assert_(get_stats(db)["total_records"] == 3)),
            ("stats_domains", lambda: assert_(get_stats(db)["unique_domains"] == 2)),
            ("stats_urls", lambda: assert_(get_stats(db)["unique_urls"] == 3)),
            (
                "top_items",
                lambda: (
                    (r := get_top_items(db, 2)),
                    assert_(len(r) == 2),
                    assert_("val" in r[0] and "cnt" in r[0]),
                ),
            ),
            (
                "time_series",
                lambda: (
                    (r := get_time_series(db)),
                    assert_(len(r) >= 1),
                    assert_("date" in r[0] and "count" in r[0]),
                ),
            ),
            (
                "domain_breakdown",
                lambda: (
                    (r := get_domain_breakdown(db)),
                    assert_(len(r) == 2),
                    assert_(r[0]["domain"] == "a.com"),
                    assert_(r[0]["count"] == 2),
                ),
            ),
            ("records_all", lambda: assert_(len(get_records(db)) == 3)),
            ("records_filtered", lambda: assert_(len(get_records(db, "b.com")) == 1)),
            (
                "column_names",
                lambda: (
                    (cols := get_column_names(db)),
                    assert_("title" in cols),
                    assert_("price" in cols),
                ),
            ),
        ]

        for name, test_fn in query_tests:
            try:
                test_fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
                errors.append((f"queries.{name}", e))

    # ===== Starlette app tests =====
    print()
    print("=" * 60)
    print("test_dashboard_app.py")
    print("=" * 60)

    from starlette.testclient import TestClient

    from dashboard.app import app

    with tempfile.TemporaryDirectory() as tmpdir:
        db = make_test_db(tmpdir)
        from pathlib import Path as _P

        from dashboard import app as dash_app

        dash_app.DB_PATH = _P(db)

        client = TestClient(app)

        app_tests = [
            ("homepage_200", lambda: assert_(client.get("/").status_code == 200)),
            (
                "homepage_has_charts",
                lambda: (
                    (r := client.get("/")),
                    assert_("chart" in r.text.lower() or "Chart" in r.text),
                ),
            ),
            (
                "api_stats",
                lambda: (
                    (r := client.get("/api/stats")),
                    assert_(r.status_code == 200),
                    assert_(r.json()["total_records"] == 3),
                ),
            ),
            (
                "api_top",
                lambda: (
                    (r := client.get("/api/top?n=2")),
                    assert_(r.status_code == 200),
                    assert_(len(r.json()) == 2),
                ),
            ),
            ("api_timeseries", lambda: assert_(client.get("/api/timeseries").status_code == 200)),
            (
                "api_domains",
                lambda: (
                    (r := client.get("/api/domains")),
                    assert_(r.status_code == 200),
                    assert_(len(r.json()) == 2),
                ),
            ),
            (
                "api_records",
                lambda: (
                    (r := client.get("/api/records")),
                    assert_(r.status_code == 200),
                    assert_(len(r.json()) == 3),
                ),
            ),
            (
                "api_records_filtered",
                lambda: (
                    (r := client.get("/api/records?domain=b.com")),
                    assert_(len(r.json()) == 1),
                ),
            ),
            (
                "api_export_csv",
                lambda: (
                    (r := client.get("/api/export?format=csv")),
                    assert_(r.status_code == 200),
                    assert_("text/csv" in r.headers["content-type"]),
                ),
            ),
            (
                "api_export_json",
                lambda: (
                    (r := client.get("/api/export?format=json")),
                    assert_(r.status_code == 200),
                    assert_(isinstance(r.json(), list)),
                ),
            ),
        ]

        for name, test_fn in app_tests:
            try:
                test_fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
                errors.append((f"app.{name}", e))

    # ===== CLI test =====
    print()
    print("=" * 60)
    print("CLI test")
    print("=" * 60)

    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "etl", "dashboard", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent),
    )
    try:
        assert_(result.returncode == 0, f"Exit code: {result.returncode}")
        assert_("port" in result.stdout.lower(), "Missing --port in help")
        print("  ✓ cli_dashboard_help")
        passed += 1
    except Exception as e:
        print(f"  ✗ cli_dashboard_help: {e}")
        failed += 1
        errors.append(("cli.dashboard", e))

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
