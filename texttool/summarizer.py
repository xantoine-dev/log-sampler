"""Summarization logic for the CLI tool."""

from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from .streaming import LineStreamConfig, iter_lines

WORD_PATTERN = re.compile(r"[a-zA-Z0-9_]{3,}")
TIMESTAMP_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")

DEFAULT_SEVERITY_KEYWORDS: dict[str, Sequence[str]] = {
    "critical": ("critical", "panic", "fatal"),
    "error": ("error", "failed", "failure", "exception"),
    "warning": ("warning", "warn", "deprecated"),
    "debug": ("debug", "trace"),
}


@dataclass
class LogSummary:
    path: str
    total_lines: int
    total_bytes: int
    severity_counts: dict[str, int]
    top_tokens: list[tuple[str, int]]
    first_timestamp: str | None
    last_timestamp: str | None
    sample: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "total_lines": self.total_lines,
            "total_bytes": self.total_bytes,
            "severity_counts": self.severity_counts,
            "top_tokens": self.top_tokens,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "sample": self.sample,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LogSummary:
        return cls(
            path=str(data["path"]),
            total_lines=int(data["total_lines"]),
            total_bytes=int(data["total_bytes"]),
            severity_counts=dict(data["severity_counts"]),
            top_tokens=[tuple(item) for item in data["top_tokens"]],
            first_timestamp=data.get("first_timestamp"),
            last_timestamp=data.get("last_timestamp"),
            sample=list(data.get("sample", [])),
        )


@dataclass
class BenchmarkObservation:
    strategy: str
    seconds: float
    per_line_microseconds: float


def _tokenize(line: str) -> Iterable[str]:
    return WORD_PATTERN.findall(line.lower())


def _maybe_extract_timestamp(line: str) -> str | None:
    match = TIMESTAMP_PATTERN.search(line)
    return match.group(1) if match else None


def _detect_severity(line: str, keywords: dict[str, Sequence[str]]) -> str:
    lowered = line.lower()
    for severity, tokens in keywords.items():
        if any(token in lowered for token in tokens):
            return severity
    return "info"


def _summarize_lines(
    lines: Iterable[str],
    *,
    path: str,
    top_words: int,
    severity_keywords: dict[str, Sequence[str]],
    sample_size: int = 5,
) -> LogSummary:
    severity_counts: dict[str, int] = {key: 0 for key in severity_keywords}
    severity_counts.setdefault("info", 0)
    token_counter: Counter[str] = Counter()
    total_lines = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    sample: list[str] = []
    path_obj = Path(path)
    total_bytes = path_obj.stat().st_size if path_obj.exists() else 0

    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\n")
        total_lines += 1

        timestamp = _maybe_extract_timestamp(line)
        if timestamp and not first_timestamp:
            first_timestamp = timestamp
        if timestamp:
            last_timestamp = timestamp

        severity = _detect_severity(line, severity_keywords)
        severity_counts.setdefault(severity, 0)
        severity_counts[severity] += 1

        for token in _tokenize(line):
            token_counter[token] += 1

        if idx < sample_size:
            sample.append(line)

    top_tokens = token_counter.most_common(top_words)
    return LogSummary(
        path=path,
        total_lines=total_lines,
        total_bytes=total_bytes,
        severity_counts=severity_counts,
        top_tokens=top_tokens,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        sample=sample,
    )


def summarize_file_baseline(
    path: Path | str,
    *,
    top_words: int = 10,
    severity_keywords: dict[str, Sequence[str]] | None = None,
) -> LogSummary:
    """Naive summarizer that loads the entire file into memory."""

    severity_keywords = severity_keywords or DEFAULT_SEVERITY_KEYWORDS
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    return _summarize_lines(
        lines,
        path=str(path),
        top_words=top_words,
        severity_keywords=severity_keywords,
    )


def summarize_file_streaming(
    path: Path | str,
    *,
    top_words: int = 10,
    severity_keywords: dict[str, Sequence[str]] | None = None,
    chunk_size: int = 1024 * 1024,
) -> LogSummary:
    """Optimized summarizer that streams lines without loading everything."""

    severity_keywords = severity_keywords or DEFAULT_SEVERITY_KEYWORDS
    config = LineStreamConfig(chunk_size=chunk_size)
    line_iterable = iter_lines(path, config=config)
    return _summarize_lines(
        line_iterable,
        path=str(path),
        top_words=top_words,
        severity_keywords=severity_keywords,
    )


def summarize(
    path: Path | str,
    *,
    strategy: str = "streaming",
    top_words: int = 10,
    severity_keywords: dict[str, Sequence[str]] | None = None,
    chunk_size: int = 1024 * 1024,
) -> LogSummary:
    strategy = strategy.lower()
    if strategy == "baseline":
        return summarize_file_baseline(
            path,
            top_words=top_words,
            severity_keywords=severity_keywords,
        )
    if strategy in {"streaming", "optimized"}:
        return summarize_file_streaming(
            path,
            top_words=top_words,
            severity_keywords=severity_keywords,
            chunk_size=chunk_size,
        )
    raise ValueError(f"Unknown strategy '{strategy}'")


def compare_strategies(
    path: Path | str,
    *,
    top_words: int = 10,
    severity_keywords: dict[str, Sequence[str]] | None = None,
    chunk_size: int = 1024 * 1024,
    repeats: int = 3,
) -> tuple[LogSummary, list[BenchmarkObservation]]:
    """Run both baseline and streaming strategies and capture timings."""

    observations: list[BenchmarkObservation] = []
    summary: LogSummary | None = None

    for strategy in ("baseline", "streaming"):
        runtimes: list[float] = []
        last_result: LogSummary | None = None
        for _ in range(repeats):
            start = time.perf_counter()
            current = summarize(
                path,
                strategy=strategy,
                top_words=top_words,
                severity_keywords=severity_keywords,
                chunk_size=chunk_size,
            )
            duration = time.perf_counter() - start
            runtimes.append(duration)
            last_result = current
            if strategy != "baseline":
                summary = current
        assert last_result is not None
        avg_duration = mean(runtimes)
        if last_result.total_lines:
            per_line = avg_duration / last_result.total_lines * 1e6
        else:
            per_line = 0.0
        observations.append(
            BenchmarkObservation(
                strategy=strategy,
                seconds=avg_duration,
                per_line_microseconds=per_line,
            )
        )

    assert summary is not None
    return summary, observations
