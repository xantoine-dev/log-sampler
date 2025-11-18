# Text Processing Command-Line Tool

[![python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![ci](https://img.shields.io/badge/CI-GitHub%20Actions-blue?logo=github)](.github/workflows/ci.yml)
[![coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](docs/coverage.md)

A UNIX-style Python CLI that ingests massive text logs, streams them line-by-line, and produces human-friendly summaries. The tool highlights error hot spots, top tokens, timestamp ranges, and lets you benchmark the naive “read everything” approach against the optimized streaming pipeline. Caching makes repeat runs nearly instant, which is perfect for on-call triage and observability work.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Benchmarking & Profiling](#benchmarking--profiling)
- [Testing & Quality Gates](#testing--quality-gates)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Changelog](#changelog)

## Features
- **Streaming summarization** – custom iterators in `texttool.streaming` keep memory flat, even for multi-GB files.
- **Rich stats** – totals, severity counts, top tokens, timestamp bounds, and sample lines to orient quickly.
- **Disk-backed memoization** – summaries are cached by path/mtime/size, turning repeat runs into ~120ms lookups.
- **Baseline vs. optimized benchmarking** – run both strategies and capture per-line microsecond metrics.
- **Built-in profiling** – `--profile` pipes the summarization step through `cProfile` for micro-optimizations.
- **Professional tooling** – Ruff + Black lint/format, pytest coverage gates, GitHub Actions CI, and reproducible synthetic data generators.

## Architecture
```
texttool/
  cli.py          # argparse entry point, caching + benchmark orchestration
  summarizer.py   # shared summarization core + baseline/streaming strategies
  streaming.py    # buffered iterators/generators for large file handling
  cache.py        # JSON-based memoization keyed by file metadata
benchmarks/
  generate_sample_log.py  # deterministic synthetic log generator
  results.md              # captured before/after metrics
benchmark.py              # convenience wrapper to synthesize + compare runs
```

## Getting Started
1. **Prerequisites**
   - Python 3.11+
   - `pip` (ships with Python)
2. **Install (editable mode for development)**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
3. **Regenerate sample data (optional)**
   ```bash
   python3.11 benchmarks/generate_sample_log.py sample_logs/synthetic.log --lines 200000
   ```

## Usage
Summarize any log file (streaming strategy, cache enabled by default):
```bash
python3.11 -m texttool.cli summarize /path/to/log --top-words 20
```
Helpful flags:
- `--strategy baseline|streaming` – compare naive vs. streaming summarizers.
- `--no-cache` – bypass the memoization layer (cache lives at `~/.cache/text_processing_cli/summaries.json`).
- `--json` – emit machine-readable output for scripts/dashboards.
- `--profile` – capture cProfile stats (top 25 rows printed to stdout).
- `--compare --repeats N` – benchmark both strategies and print a timing table.

## Benchmarking & Profiling
Generate a deterministic log and compare strategies in one command:
```bash
python3.11 benchmark.py sample_logs/synthetic.log --generate --lines 300000 --repeats 3
```
A manual benchmark produced the following “before vs. after” highlights (see `benchmarks/results.md` for raw data):
- Baseline read-all strategy: **~2.00 s** for a 200k-line log.
- Streaming iterator: **~1.98 s** for the same log with flat memory usage.
- Cache hit: **~0.12 s** after the summary is memoized, ideal for repeat investigations.

## Testing & Quality Gates
Quality tooling follows [PEP 8](https://peps.python.org/pep-0008/) via Black + Ruff.
```bash
ruff check .
black .
python3.11 -m pytest       # runs with coverage + 85% gate
```
CI mirrors these steps in `.github/workflows/ci.yml`. Coverage snapshots are stored in [`docs/coverage.md`](docs/coverage.md).

## Project Structure
```
.
├── texttool/           # Core package
├── benchmarks/         # Synthetic data + captured metrics
├── sample_logs/        # Empty placeholder folder (logs are .gitignored)
├── tests/              # Pytest suite covering cache, streaming, summarizer
├── docs/coverage.md    # Latest coverage summary
├── CHANGELOG.md        # Release history
└── pyproject.toml      # Tooling/lint/test configuration
```

## Contributing
1. Fork & clone the repository.
2. Create a virtualenv + install dev dependencies (`pip install -e .[dev]`).
3. Run `ruff`, `black`, and `pytest` locally before opening a PR.
4. Follow conventional commit messages or squash into logical commits (e.g., `feat: add streaming iterator`, `docs: expand README`).
5. Update `CHANGELOG.md` and `docs/coverage.md` when behavior changes.

## Changelog
See [`CHANGELOG.md`](CHANGELOG.md) for release notes. Versioning follows SemVer; the current release is **0.1.0**.
