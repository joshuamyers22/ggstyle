"""Bounded time and memory benchmark for semantic rendering."""

from __future__ import annotations

import argparse
import tracemalloc
from dataclasses import dataclass
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ggstyle as gs


@dataclass(frozen=True)
class Measurement:
    """One semantic workload measurement."""

    rows: int
    elapsed: float
    peak_bytes: int
    artists: int


def run(rows: int, *, track_memory: bool = False) -> Measurement:
    """Render representative line, point, ribbon, and guide semantics."""

    index = np.arange(rows)
    x = index.astype(float)
    center = np.sin(index / 300.0)
    series = np.asarray([f"S{value}" for value in index % 8])
    data = {
        "x": x,
        "value": center,
        "low": center - 0.15,
        "high": center + 0.15,
        "series": series,
        "score": index.astype(float) / max(rows - 1, 1),
    }
    figure, ax = plt.subplots()
    if track_memory:
        tracemalloc.start()
    started = perf_counter()
    try:
        line = gs.line(data, x="x", y="value", color="series", ax=ax)
        points = gs.points(data, x="x", y="value", color="score", ax=ax)
        ribbon = gs.ribbon(
            data,
            x="x",
            lower="low",
            upper="high",
            color="series",
            ax=ax,
        )
        guides = gs.guides(ax)
        elapsed = perf_counter() - started
        peak = tracemalloc.get_traced_memory()[1] if track_memory else 0
        artists = (
            len(line.artists)
            + len(points.artists)
            + len(ribbon.artists)
            + len(guides.legends)
            + len(guides.colorbars)
        )
        if artists != 19:
            raise RuntimeError(f"expected 19 semantic artists, found {artists}")
        return Measurement(rows, elapsed, peak, artists)
    finally:
        if track_memory:
            tracemalloc.stop()
        plt.close(figure)


def main() -> None:
    """Run representative sizes and reject gross complexity regressions."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-seconds", type=float, default=15.0)
    parser.add_argument("--max-peak-mib", type=float, default=128.0)
    parser.add_argument("--max-growth", type=float, default=9.0)
    arguments = parser.parse_args()

    small = run(10_000)
    large = run(50_000)
    memory = run(25_000, track_memory=True)
    time_growth = large.elapsed / max(small.elapsed, 1e-9)
    peak_mib = memory.peak_bytes / (1024 * 1024)
    print(
        "semantic benchmark: "
        f"{large.elapsed:.3f}s, {peak_mib:.1f} MiB peak, "
        f"{large.rows:,} rows, {large.artists} artists, "
        f"growth {time_growth:.2f}x time, {memory.rows:,}-row memory sample"
    )
    if large.elapsed > arguments.max_seconds:
        raise RuntimeError(
            f"semantic render took {large.elapsed:.3f}s; "
            f"limit is {arguments.max_seconds:.3f}s"
        )
    if peak_mib > arguments.max_peak_mib:
        raise RuntimeError(
            f"semantic render peaked at {peak_mib:.1f} MiB; "
            f"limit is {arguments.max_peak_mib:.1f} MiB"
        )
    if time_growth > arguments.max_growth:
        raise RuntimeError(
            "semantic workload growth exceeded the bounded linearity guard: "
            f"{time_growth:.2f}x time for 5x rows"
        )


if __name__ == "__main__":
    main()
