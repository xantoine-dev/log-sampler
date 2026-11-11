"""Command-line interface for the streaming text summarizer."""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from .cache import SummaryCache, get_cache
from .summarizer import BenchmarkObservation, LogSummary, compare_strategies, summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Streaming text log summarizer")
    subparsers = parser.add_subparsers(dest="command")

    summarize_parser = subparsers.add_parser("summarize", help="Summarize a log file")
    _augment_summarize_parser(summarize_parser)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark baseline vs optimized strategies",
    )
    _augment_summarize_parser(benchmark_parser, include_compare=False)
    benchmark_parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of runs per strategy",
    )

    parser.set_defaults(command="summarize")
    return parser


def _augment_summarize_parser(
    parser: argparse.ArgumentParser,
    *,
    include_compare: bool = True,
) -> None:
    parser.add_argument("path", help="Path to the log file")
    parser.add_argument(
        "--top-words",
        type=int,
        default=10,
        help="How many of the most common tokens to show",
    )
    parser.add_argument(
        "--strategy",
        choices=("baseline", "streaming"),
        default="streaming",
        help="Summarization strategy to use",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="Chunk size for streaming reads",
    )
    parser.add_argument(
        "--no-cache",
        action="store_false",
        dest="cache",
        help="Disable memoized summaries",
    )
    parser.add_argument("--cache", action="store_true", dest="cache", help=argparse.SUPPRESS)
    parser.set_defaults(cache=True)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Profile the summarization step with cProfile",
    )
    if include_compare:
        parser.add_argument(
            "--compare",
            action="store_true",
            help="Benchmark baseline vs optimized strategies",
        )
        parser.add_argument(
            "--repeats",
            type=int,
            default=3,
            help="Benchmark repetitions per strategy",
        )


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "summarize":
        _run_summarize(args)
    elif args.command == "benchmark":
        _run_benchmark(args)
    else:  # pragma: no cover - defensive programming
        parser.error(f"Unknown command: {args.command}")


def _run_summarize(args: argparse.Namespace) -> None:
    path = Path(args.path)
    if not path.exists():
        sys.exit(f"File not found: {path}")

    cache: SummaryCache | None = get_cache(args.cache)
    summary: LogSummary | None = None
    observations: list[BenchmarkObservation] | None = None

    if cache and not args.compare:
        cached = cache.get(path, top_words=args.top_words)
        if cached:
            summary = LogSummary.from_dict(cached)
            print("Loaded summary from cache", file=sys.stderr)

    if summary is None:
        if args.compare:
            summary, observations = compare_strategies(
                path,
                top_words=args.top_words,
                chunk_size=args.chunk_size,
                repeats=args.repeats,
            )
        else:
            summary = _maybe_profile(
                args.profile,
                lambda: summarize(
                    path,
                    strategy=args.strategy,
                    top_words=args.top_words,
                    chunk_size=args.chunk_size,
                ),
            )
        if cache:
            cache.set(path, summary.to_dict(), top_words=args.top_words)

    _render_summary(summary, as_json=args.json)
    if observations:
        _render_benchmarks(observations)


def _run_benchmark(args: argparse.Namespace) -> None:
    path = Path(args.path)
    summary, observations = compare_strategies(
        path,
        top_words=args.top_words,
        chunk_size=args.chunk_size,
        repeats=args.repeats,
    )
    _render_summary(summary, as_json=args.json)
    _render_benchmarks(observations)


def _maybe_profile(enabled: bool, func: Callable[[], LogSummary]) -> LogSummary:
    if not enabled:
        return func()

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        return func()
    finally:
        profiler.disable()
        buffer = io.StringIO()
        stats = pstats.Stats(profiler, stream=buffer).sort_stats("cumulative")
        stats.print_stats(25)
        print("\n--- cProfile (top 25 cumulative) ---")
        print(buffer.getvalue())


def _render_summary(summary: LogSummary, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary.to_dict(), indent=2))
        return

    print(f"Summary for {summary.path}")
    print("=" * (12 + len(summary.path)))
    print(f"Total lines : {summary.total_lines:,}")
    print(f"Total bytes : {summary.total_bytes:,}")
    print("Severity counts:")
    for severity, count in sorted(summary.severity_counts.items()):
        print(f"  - {severity:<8} {count:,}")
    print("Top tokens:")
    for token, count in summary.top_tokens:
        print(f"  - {token:<15} {count:,}")
    if summary.first_timestamp or summary.last_timestamp:
        print(f"First timestamp: {summary.first_timestamp}")
        print(f"Last timestamp : {summary.last_timestamp}")
    if summary.sample:
        print("Sample lines:")
        for line in summary.sample:
            print(f"  {line}")


def _render_benchmarks(observations: list[BenchmarkObservation]) -> None:
    print("\nBenchmark (average per strategy)")
    print("Strategy      Seconds   usec/line")
    for obs in observations:
        print(f"{obs.strategy:<12} {obs.seconds:>7.4f}   {obs.per_line_microseconds:>9.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
