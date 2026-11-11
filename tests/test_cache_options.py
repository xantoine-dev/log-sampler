"""Regression coverage for option-sensitive cached summaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from texttool.cache import SummaryCache


@pytest.fixture()
def token_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / "tokens.log"
    path.write_text("alpha alpha beta gamma delta\n", encoding="utf-8")
    return path


def run_summary(path: Path, top_words: int, *, cached: bool = True) -> tuple[dict, str]:
    command = [
        sys.executable,
        "-m",
        "texttool.cli",
        "summarize",
        str(path),
        "--top-words",
        str(top_words),
        "--json",
    ]
    if not cached:
        command.append("--no-cache")
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout), result.stderr


@pytest.mark.parametrize("first,second", [(1, 3), (3, 1)])
def test_cli_changed_top_words_matches_uncached_result(
    token_log: Path, first: int, second: int
) -> None:
    expected_tokens = [["alpha", 2], ["beta", 1], ["gamma", 1]]
    initial, stderr = run_summary(token_log, first)
    assert initial["top_tokens"] == expected_tokens[:first]
    assert "Loaded summary from cache" not in stderr

    uncached, _ = run_summary(token_log, second, cached=False)
    assert uncached["top_tokens"] == expected_tokens[:second]
    changed, stderr = run_summary(token_log, second)
    assert changed == uncached
    assert "Loaded summary from cache" not in stderr

    repeated, stderr = run_summary(token_log, second)
    assert repeated == uncached
    assert "Loaded summary from cache" in stderr


def test_cli_source_edit_invalidates_same_option_cache(token_log: Path) -> None:
    run_summary(token_log, 3)
    token_log.write_text("beta beta beta beta alpha\n", encoding="utf-8")

    result, stderr = run_summary(token_log, 3)
    uncached, _ = run_summary(token_log, 3, cached=False)
    assert result["top_tokens"] == [["beta", 4], ["alpha", 1]]
    assert result == uncached
    assert "Loaded summary from cache" not in stderr


def test_cli_legacy_cache_entry_recomputes(token_log: Path) -> None:
    truncated, _ = run_summary(token_log, 1, cached=False)
    stats = token_log.stat()
    cache_file = token_log.parent / ".cache" / "text_processing_cli" / "summaries.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(
        json.dumps(
            {
                str(token_log.resolve()): {
                    "size": stats.st_size,
                    "mtime": stats.st_mtime,
                    "summary": truncated,
                }
            }
        )
    )

    result, stderr = run_summary(token_log, 3)
    assert result["top_tokens"] == [["alpha", 2], ["beta", 1], ["gamma", 1]]
    assert "Loaded summary from cache" not in stderr
    repeated, stderr = run_summary(token_log, 3)
    assert repeated == result
    assert "Loaded summary from cache" in stderr


def test_cache_reloaded_entry_requires_matching_top_words(token_log: Path) -> None:
    cache_file = token_log.parent / "options-cache.json"
    payload = {"top_tokens": [["alpha", 2]]}
    SummaryCache(cache_file).set(token_log, payload, top_words=1)

    cache = SummaryCache(cache_file)
    assert cache.get(token_log, top_words=1) == payload
    assert cache.get(token_log, top_words=3) is None
    assert cache.get(token_log) is None
