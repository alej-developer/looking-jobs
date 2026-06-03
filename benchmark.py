"""
benchmark.py — Performance benchmarking for the ATS Job Automator.

Measures execution time and peak RAM consumption of the scraper pipeline.
Results are written to a structured JSON log file for tracking across runs.
Uses memory_profiler for accurate RSS measurement and time.perf_counter
for high-resolution wall-clock timing.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
from memory_profiler import memory_usage

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────
_RESULTS_DIR = Path(__file__).resolve().parent / "benchmark_results"
_RESULTS_FILE = _RESULTS_DIR / "benchmark_log.jsonl"


# ─── Benchmark Wrapper ──────────────────────────────────────────────────────

def _run_scraper_sync() -> dict[str, int]:
    """Synchronous wrapper around the async scraper for memory_profiler compatibility.

    Returns:
        The summary dict from run_scraper().
    """
    from scraper import run_scraper

    return asyncio.run(run_scraper())


def run_benchmark() -> dict:
    """Execute the scraper pipeline and measure performance metrics.

    Captures:
    - **Wall-clock time** via ``time.perf_counter`` (high-resolution).
    - **Peak RAM (MiB)** via ``memory_profiler.memory_usage`` (RSS-based).
    - **CPU usage %** via ``psutil.Process`` snapshots.
    - **Scraper summary** (offers inserted, errors).

    Results are appended as a JSON line to ``benchmark_results/benchmark_log.jsonl``.

    Returns:
        A dict with all benchmark metrics and the scraper summary.
    """
    process = psutil.Process(os.getpid())

    logger.info("=" * 60)
    logger.info("BENCHMARK — Starting performance measurement")
    logger.info("=" * 60)

    # ── Capture baseline metrics ─────────────────────────────────────────
    cpu_before = process.cpu_percent(interval=None)  # prime the counter
    baseline_mem = process.memory_info().rss / (1024 * 1024)  # MiB

    # ── Run scraper with memory profiling ────────────────────────────────
    start_time = time.perf_counter()

    mem_samples, scraper_result = memory_usage(
        proc=(_run_scraper_sync, (), {}),
        interval=0.5,          # sample every 500ms
        timestamps=False,
        retval=True,
        max_usage=False,
    )

    end_time = time.perf_counter()

    # ── Calculate metrics ────────────────────────────────────────────────
    elapsed_seconds = round(end_time - start_time, 3)
    peak_memory_mib = round(max(mem_samples), 2) if mem_samples else 0.0
    avg_memory_mib = round(sum(mem_samples) / len(mem_samples), 2) if mem_samples else 0.0
    cpu_after = process.cpu_percent(interval=0.5)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "peak_memory_mib": peak_memory_mib,
        "avg_memory_mib": avg_memory_mib,
        "baseline_memory_mib": round(baseline_mem, 2),
        "memory_samples_count": len(mem_samples),
        "cpu_percent": round(cpu_after, 1),
        "python_version": sys.version,
        "scraper_summary": scraper_result if isinstance(scraper_result, dict) else {},
    }

    # ── Persist results ──────────────────────────────────────────────────
    _save_result(result)

    # ── Log summary ──────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("BENCHMARK RESULTS")
    logger.info("-" * 60)
    logger.info("  Execution time : %s seconds", result["elapsed_seconds"])
    logger.info("  Peak RAM       : %s MiB", result["peak_memory_mib"])
    logger.info("  Avg RAM        : %s MiB", result["avg_memory_mib"])
    logger.info("  Baseline RAM   : %s MiB", result["baseline_memory_mib"])
    logger.info("  CPU usage      : %s%%", result["cpu_percent"])
    logger.info("  Memory samples : %d", result["memory_samples_count"])
    logger.info("  Offers inserted: %s", result["scraper_summary"].get("total_inserted", "N/A"))
    logger.info("  Errors         : %s", result["scraper_summary"].get("total_errors", "N/A"))
    logger.info("=" * 60)

    return result


def _save_result(result: dict) -> None:
    """Append a benchmark result as a JSON line to the log file.

    Creates the benchmark_results/ directory if it doesn't exist.

    Args:
        result: The benchmark metrics dict to persist.
    """
    try:
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
        logger.info("Benchmark results saved to %s", _RESULTS_FILE)
    except OSError:
        logger.exception("Failed to save benchmark results to %s", _RESULTS_FILE)


# ─── Script Execution ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run_benchmark()
