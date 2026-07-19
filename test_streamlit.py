"""Tests para Streamlit dashboard (data loading + chart generation)."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import sys
sys.path.insert(0, str(Path(__file__).parent))


def assert_(condition, msg="Assertion failed"):
    if not condition:
        raise AssertionError(msg)


def create_test_db(tmpdir) -> Path:
    """Crea una DB de prueba con datos de ejemplo."""
    db_path = Path(tmpdir) / "test.db"
    conn = sqlite3.connect(str(db_path))

    # raw_data table
    conn.execute("""CREATE TABLE raw_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url TEXT,
        source_domain TEXT,
        data TEXT,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    items = [
        {"title": "Laptop Pro", "price": "$1299", "category": "electronics"},
        {"title": "Mouse RGB", "price": "$45", "category": "electronics"},
        {"title": "Book Python", "price": "$25", "category": "books"},
        {"title": "Keyboard Mech", "price": "$89", "category": "electronics"},
        {"title": "Book Data", "price": "$30", "category": "books"},
    ]
    for i, item in enumerate(items):
        conn.execute(
            "INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
            (f"http://test{i}.com/products", f"test{i}.com", json.dumps([item])),
        )

    conn.commit()
    conn.close()
    return db_path


def run_tests():
    passed = 0
    failed = 0
    errors = []

    # ===== Data Loading Tests =====
    print("=" * 60)
    print("test_streamlit_data.py")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = create_test_db(tmpdir)

        # Import the data loading functions
        from dashboard.streamlit_app import load_data, load_processed_data

        load_tests = [
            ("load_data_returns_df", lambda: (
                (df := load_data(str(db_path))),
                assert_(isinstance(df, pd.DataFrame)),
                assert_(len(df) == 5, f"Expected 5, got {len(df)}"),
            )),
            ("load_data_has_columns", lambda: (
                (df := load_data(str(db_path))),
                assert_("title" in df.columns),
                assert_("_source_url" in df.columns),
                assert_("_source_domain" in df.columns),
            )),
            ("load_data_metadata", lambda: (
                (df := load_data(str(db_path))),
                assert_(df["_source_url"].iloc[0] == "http://test0.com/products"),
                assert_(df["_source_domain"].iloc[0] == "test0.com"),
            )),
            ("load_data_empty_db", lambda: (
                (empty_db := Path(tmpdir) / "empty.db"),
                (conn := sqlite3.connect(str(empty_db))),
                conn.execute("""CREATE TABLE raw_data (
                    id INTEGER PRIMARY KEY, source_url TEXT,
                    source_domain TEXT, data TEXT, scraped_at TIMESTAMP
                )"""),
                conn.close(),
                (df := load_data(str(empty_db))),
                assert_(df.empty),
            )),
            ("load_data_missing_db", lambda: (
                (df := load_data(str(Path(tmpdir) / "nonexistent.db"))),
                assert_(df.empty),
            )),
            ("load_processed_data_empty", lambda: (
                (df := load_processed_data(str(db_path))),
                assert_(df.empty),  # No processed_data table yet
            )),
        ]

        for name, test_fn in load_tests:
            try:
                test_fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
                errors.append((f"data.{name}", e))

    # ===== Chart Generation Tests =====
    print()
    print("=" * 60)
    print("test_streamlit_charts.py")
    print("=" * 60)

    df_sample = pd.DataFrame({
        "title": ["Laptop", "Mouse", "Keyboard", "Monitor", "USB Cable"],
        "price": ["$1299", "$45", "$89", "$299", "$12"],
        "category": ["electronics", "electronics", "electronics", "electronics", "accessories"],
        "_source_url": ["http://a.com", "http://a.com", "http://b.com", "http://b.com", "http://c.com"],
        "_source_domain": ["a.com", "a.com", "b.com", "b.com", "c.com"],
    })

    def _test_bar_chart(df):
        counts = df["title"].value_counts().head(10).reset_index()
        counts.columns = ["title", "count"]
        fig = px.bar(counts, x="title", y="count")
        assert_(isinstance(fig, go.Figure))
        assert_(len(fig.data) > 0)

    def _test_donut_chart(df):
        domain_counts = df["_source_domain"].value_counts().reset_index()
        domain_counts.columns = ["domain", "count"]
        fig = px.pie(domain_counts, names="domain", hole=0.4)
        assert_(isinstance(fig, go.Figure))

    chart_tests = [
        ("bar_chart", lambda: _test_bar_chart(df_sample)),
        ("donut_chart", lambda: _test_donut_chart(df_sample)),
        ("histogram", lambda: (
            (fig := px.histogram(df_sample, x="title")),
            assert_(isinstance(fig, go.Figure)),
        )),
    ]

    for name, test_fn in chart_tests:
        try:
            test_fn()
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
            errors.append((f"chart.{name}", e))

    # ===== CLI Tests =====
    print()
    print("=" * 60)
    print("CLI tests")
    print("=" * 60)

    import subprocess

    # Test --help shows streamlit mode
    result = subprocess.run(
        [sys.executable, "-m", "etl", "dashboard", "--help"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent),
    )
    try:
        assert_(result.returncode == 0, f"Exit code: {result.returncode}")
        assert_("streamlit" in result.stdout, "Missing 'streamlit' in help")
        assert_("starlette" in result.stdout, "Missing 'starlette' in help")
        print("  ✓ cli_dashboard_modes")
        passed += 1
    except Exception as e:
        print(f"  ✗ cli_dashboard_modes: {e}")
        failed += 1
        errors.append(("cli.modes", e))

    # Test main --help
    result = subprocess.run(
        [sys.executable, "-m", "etl", "--help"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent),
    )
    try:
        assert_(result.returncode == 0)
        assert_("dashboard" in result.stdout)
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
