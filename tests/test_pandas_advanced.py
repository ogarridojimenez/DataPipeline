"""Tests para transformaciones avanzadas con pandas."""

import pandas as pd
import pytest

from etl.process import compute_summary, group_by_domain, pipeline_pipe


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "_source_domain": ["a.com", "a.com", "b.com", "b.com"],
            "value": [10, 20, 30, 40],
            "category": ["x", "y", "x", "y"],
        }
    )


class TestComputeSummary:
    def test_basic_counts(self, sample_df):
        s = compute_summary(sample_df)
        assert s["total_records"] == 4
        assert s["numeric_columns"] == 1

    def test_numeric_stats(self, sample_df):
        s = compute_summary(sample_df)
        assert "numeric_stats" in s
        assert s["numeric_stats"]["value"]["mean"] == 25.0

    def test_empty_df(self):
        s = compute_summary(pd.DataFrame())
        assert s == {}


class TestGroupByDomain:
    def test_groups_by_domain(self, sample_df):
        gb = group_by_domain(sample_df)
        assert len(gb) == 2

    def test_empty_df(self):
        gb = group_by_domain(pd.DataFrame())
        assert gb.empty


class TestPipelinePipe:
    def test_filter_gt(self, sample_df):
        result = pipeline_pipe(sample_df, [{"type": "filter", "params": {"column": "value", "op": "gt", "value": 20}}])
        assert len(result) == 2

    def test_add_rank(self, sample_df):
        result = pipeline_pipe(sample_df, [{"type": "add_rank", "params": {"column": "value", "name": "r"}}])
        assert "r" in result.columns

    def test_sort(self, sample_df):
        result = pipeline_pipe(sample_df, [{"type": "sort", "params": {"column": "value", "ascending": False}}])
        assert result.iloc[0]["value"] == 40

    def test_top_n(self, sample_df):
        result = pipeline_pipe(sample_df, [{"type": "top_n", "params": {"column": "value", "n": 2}}])
        assert len(result) == 2

    def test_normalize_minmax(self, sample_df):
        result = pipeline_pipe(
            sample_df, [{"type": "normalize", "params": {"column": "value", "name": "v_norm", "method": "minmax"}}]
        )
        assert "v_norm" in result.columns
        assert result["v_norm"].min() == pytest.approx(0.0)
        assert result["v_norm"].max() == pytest.approx(1.0)

    def test_pipe_chaining(self, sample_df):
        steps = [
            {"type": "filter", "params": {"column": "value", "op": "gt", "value": 10}},
            {"type": "add_rank", "params": {"column": "value", "name": "r"}},
            {"type": "sort", "params": {"column": "r", "ascending": True}},
        ]
        result = pipeline_pipe(sample_df, steps)
        assert len(result) > 0
        assert "r" in result.columns
