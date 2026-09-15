"""Regenerate visual regression baselines in the pinned renderer environment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "tests"))

from visual_cases import CASES, verify_visual_environment, write_png  # noqa: E402


def main() -> int:
    """Write every canonical baseline after explicit overwrite confirmation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accept",
        action="store_true",
        help="confirm that existing reviewed baselines may be overwritten",
    )
    arguments = parser.parse_args()
    if not arguments.accept:
        parser.error("baseline replacement requires --accept")

    verify_visual_environment()
    destination = _ROOT / "tests" / "baseline_images"
    destination.mkdir(parents=True, exist_ok=True)
    for name, builder in CASES.items():
        figure = builder()
        path = destination / f"{name}.png"
        try:
            write_png(figure, path)
        finally:
            plt.close(figure)
        print(path.relative_to(_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
