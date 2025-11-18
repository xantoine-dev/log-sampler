# Benchmark Results

All tests were run with Python 3.11 on the local development machine using the synthetic log generated via

```
python3 benchmarks/generate_sample_log.py sample_logs/synthetic.log --lines 200000
```

That file contains 200,000 lines (~11 MB).

## Baseline vs. streaming iterator

Command:

```
/usr/bin/time -p python3 -m texttool.cli summarize sample_logs/synthetic.log --strategy baseline --no-cache
/usr/bin/time -p python3 -m texttool.cli summarize sample_logs/synthetic.log --no-cache
```

| Mode | Real time | Notes |
| --- | --- | --- |
| Baseline (loads entire file) | 2.00 s | Uses naive `Path.read_text().splitlines()` |
| Streaming iterator | 1.98 s | Reads lazily via `texttool.streaming.LineStream` |

The wall-clock difference is modest on this machine, but the optimized iterator keeps memory flat and scales when files exceed RAM.

Running the built-in compare command with two repetitions produced:

```
Strategy      Seconds   usec/line
baseline      1.90      9.5
streaming     1.89      9.4
```

## Memoization payoff (before vs. after)

Command:

```
/usr/bin/time -p python3 -m texttool.cli summarize sample_logs/synthetic.log
/usr/bin/time -p python3 -m texttool.cli summarize sample_logs/synthetic.log
```

| Run | Real time | Notes |
| --- | --- | --- |
| First run (fills cache) | 1.99 s | Reads & summarizes the entire log |
| Cache hit | 0.12 s | Reuses memoized summary stored in `~/.cache/text_processing_cli` |

Once the cache is warm the summary returns almost instantly. This is the primary "before vs. after optimization" result: repeated investigations go from ~2 seconds to ~120 milliseconds.

## Profiling

Use `--profile` to capture hotspots, e.g.

```
python3 -m texttool.cli summarize sample_logs/synthetic.log --profile --no-cache
```

cProfile shows the tokenizer and severity detection dominating runtime, which guided the optimizations above (streaming iterator + memoized summaries).
