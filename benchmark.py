"""Convenience runner to benchmark baseline vs optimized summarizers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.generate_sample_log import generate_log
from texttool.summarizer import compare_strategies


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Log file to benchmark")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate the log file before benchmarking",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=300_000,
        help="Line count when generating synthetic logs",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Benchmark repetitions per strategy",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON for automation")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    path = Path(args.path)
    if args.generate or not path.exists():
        generate_log(path, lines=args.lines)

    summary, observations = compare_strategies(path, repeats=args.repeats)
    if args.json:
        payload: dict[str, object] = {
            "summary": summary.to_dict(),
            "observations": [obs.__dict__ for obs in observations],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Benchmark for {path}")
        for obs in observations:
            print(
                f"{obs.strategy:<10} {obs.seconds:>7.4f}s "
                f"({obs.per_line_microseconds:>8.2f} usec/line)"
            )


if __name__ == "__main__":
    main()
