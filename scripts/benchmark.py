"""Benchmark harness: runs LogScope's summary command against a large log
file and reports processing time, peak memory usage and whether the
60-second / 100 MB acceptance target is met.

Memory is sampled with ``psutil`` (polling the process RSS from a
background thread) because Windows has no ``resource.getrusage`` peak-RSS
equivalent; this is the "appropriate measurement method available in the
environment" referred to by SPEC.md section 9. Polling only captures
memory at sampling instants, so it is an approximation of the true peak,
not an exact value.

Usage::

    python scripts/benchmark.py sample.log
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logscope.commands.summary import compute_summary  # noqa: E402

POLL_INTERVAL_SECONDS = 0.05


def _poll_peak_rss(process: psutil.Process, peak: list, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            rss = process.memory_info().rss
        except psutil.Error:
            break
        if rss > peak[0]:
            peak[0] = rss
        stop_event.wait(POLL_INTERVAL_SECONDS)


def run_benchmark(log_path: Path) -> None:
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop_event = threading.Event()
    sampler = threading.Thread(target=_poll_peak_rss, args=(process, peak, stop_event), daemon=True)
    sampler.start()

    start = time.perf_counter()
    result = compute_summary(log_path)
    elapsed = time.perf_counter() - start

    stop_event.set()
    sampler.join(timeout=1)

    size_mb = log_path.stat().st_size / (1024 * 1024)
    peak_mb = peak[0] / (1024 * 1024)
    target_met = elapsed < 60.0

    print(f"File: {log_path}")
    print(f"File size: {size_mb:.2f} MB")
    print(f"Processing time: {elapsed:.2f} s")
    print(f"Peak process memory (RSS, sampled): {peak_mb:.2f} MB")
    print(f"60-second target met: {'YES' if target_met else 'NO'}")
    print(
        "Summary result: "
        f"INFO={result.info_count} WARN={result.warn_count} ERROR={result.error_count} "
        f"malformed={result.malformed_lines}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/benchmark.py <log_file>", file=sys.stderr)
        sys.exit(2)
    run_benchmark(Path(sys.argv[1]))
