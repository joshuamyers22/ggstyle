"""Bounded smoke benchmark for observation-registry rebuilds."""

from __future__ import annotations

import argparse
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ggstyle as gs


def run() -> tuple[float, int, int]:
    """Build representative line, scatter, and multi-path polygon provenance."""
    count = 50_000
    dates = np.datetime64("2024-01-01T00:00") + np.arange(count).astype(
        "timedelta64[m]"
    )
    values = np.sin(np.arange(count, dtype=float) / 300.0)
    figure, ax = plt.subplots()
    try:
        ax.plot(dates, values)
        ax.scatter(dates[::2], values[::2], s=1)
        polygon_dates = dates[:10_000]
        where = np.arange(len(polygon_dates)) % 100 < 50
        collection = ax.fill_between(
            polygon_dates,
            values[:10_000] - 0.1,
            values[:10_000] + 0.1,
            where=where,
        )
        started = perf_counter()
        handle = gs.dates(ax).collapse()
        handle.refresh()
        elapsed = perf_counter() - started
        observations = len(handle.observations)
        paths = len(collection.get_paths())
        if observations != count:
            raise RuntimeError(f"expected {count} observations, found {observations}")
        return elapsed, observations, paths
    finally:
        plt.close(figure)


def main() -> None:
    """Run the benchmark and reject only gross complexity regressions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-seconds", type=float, default=15.0)
    arguments = parser.parse_args()
    elapsed, observations, paths = run()
    print(
        f"registry benchmark: {elapsed:.3f}s, "
        f"{observations:,} observations, {paths} polygon paths"
    )
    if elapsed > arguments.max_seconds:
        raise RuntimeError(
            f"registry refresh took {elapsed:.3f}s; limit is {arguments.max_seconds:.3f}s"
        )


if __name__ == "__main__":
    main()
