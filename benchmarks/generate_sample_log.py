"""Generate synthetic log files for benchmarking the CLI."""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

LEVELS = [
    ("INFO", "user login successful"),
    ("DEBUG", "cache hit for key"),
    ("WARNING", "deprecated API usage"),
    ("ERROR", "failed to connect to database"),
    ("CRITICAL", "fatal exception in worker thread"),
]


def generate_log(path: Path | str, *, lines: int, seed: int = 42) -> Path:
    random.seed(seed)
    output = Path(path)
    start = datetime.now() - timedelta(minutes=lines // 100)

    with output.open("w", encoding="utf-8") as handle:
        for i in range(lines):
            level, message = random.choice(LEVELS)
            timestamp = (start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"{timestamp} {level} [{i % 64:02x}] {message}\n")

    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Where to write the generated log file")
    parser.add_argument("--lines", type=int, default=200_000, help="How many lines to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = generate_log(args.path, lines=args.lines, seed=args.seed)
    print(f"Wrote {args.lines:,} lines to {path}")


if __name__ == "__main__":
    main()
