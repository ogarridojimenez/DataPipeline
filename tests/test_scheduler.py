"""Tests para etl.scheduler — programación de tareas ETL."""

from __future__ import annotations

from etl.scheduler import load_schedule, remove_task, save_schedule


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr("etl.scheduler._schedule_path", lambda: tmp_path / "schedule.json")
    save_schedule("0 9 * * *", ["https://example.com"], ["h1"], ":memory:")
    path = tmp_path / "schedule.json"
    assert path.exists()

    loaded = load_schedule()
    assert loaded is not None
    assert loaded["cron"] == "0 9 * * *"


def test_load_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("etl.scheduler._schedule_path", lambda: tmp_path / "nonexistent.json")
    loaded = load_schedule()
    assert loaded is None


def test_remove_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr("etl.scheduler._schedule_path", lambda: tmp_path / "schedule.json")
    # Must patch remove_task to avoid calling OS-level uninstall
    import etl.scheduler as sched

    remove_task()
    assert not sched._schedule_path().exists()
