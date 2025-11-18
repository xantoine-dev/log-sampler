"""Test suite covering the public surface of the texttool package."""

from __future__ import annotations

from pathlib import Path

import pytest

from texttool.cache import SummaryCache
from texttool.streaming import LineStream, LineStreamConfig
from texttool.summarizer import LogSummary, compare_strategies, summarize


@pytest.fixture()
def sample_log(tmp_path: Path) -> Path:
    lines = [
        "2025-01-01 00:00:00 INFO start",
        "2025-01-01 00:00:01 DEBUG cache hit",
        "2025-01-01 00:00:02 WARNING deprecated",
        "2025-01-01 00:00:03 ERROR failed to connect",
        "2025-01-01 00:00:04 CRITICAL fatal exception",
    ]
    target = tmp_path / "app.log"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def test_strategies_produce_equivalent_summaries(sample_log: Path) -> None:
    baseline = summarize(sample_log, strategy="baseline", top_words=5)
    streaming = summarize(sample_log, strategy="streaming", top_words=5)
    assert baseline.to_dict() == streaming.to_dict()


def test_summary_cache_roundtrip(sample_log: Path, tmp_path: Path) -> None:
    cache_file = tmp_path / "cache" / "summaries.json"
    cache = SummaryCache(cache_file)
    summary = summarize(sample_log, strategy="streaming")
    cache.set(sample_log, summary.to_dict())
    cached = cache.get(sample_log)
    assert cached is not None
    assert LogSummary.from_dict(cached).to_dict() == summary.to_dict()


def test_summary_cache_clear(sample_log: Path, tmp_path: Path) -> None:
    cache_file = tmp_path / "cache" / "summaries.json"
    cache = SummaryCache(cache_file)
    summary = summarize(sample_log, strategy="baseline")
    cache.set(sample_log, summary.to_dict())
    cache.clear()
    assert cache.get(sample_log) is None


def test_linestream_respects_chunk_size(sample_log: Path) -> None:
    stream = LineStream(sample_log, config=LineStreamConfig(chunk_size=8))
    collected = [line.rstrip("\n") for line in stream]
    assert collected[0].startswith("2025-01-01 00:00:00 INFO")
    assert len(collected) == 5


def test_compare_strategies_reports_both_modes(sample_log: Path) -> None:
    summary, observations = compare_strategies(sample_log, repeats=1, top_words=3)
    assert summary.total_lines == 5
    strategies = {obs.strategy for obs in observations}
    assert strategies == {"baseline", "streaming"}
    assert all(obs.seconds >= 0 for obs in observations)
