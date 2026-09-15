"""Pixel regression tests for stable, user-visible rendering contracts."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
from matplotlib.testing.compare import compare_images

from visual_cases import CASES, verify_visual_environment, write_png

_ROOT = Path(__file__).resolve().parents[1]
_BASELINES = Path(__file__).with_name("baseline_images")
_RESULTS = _ROOT / "build" / "visual-results"
_TOLERANCE = 0.1

pytestmark = [
    pytest.mark.visual,
    pytest.mark.skipif(
        os.environ.get("GGSTYLE_RUN_VISUAL") != "1",
        reason="pixel tests run only in the pinned visual environment",
    ),
]


def test_visual_environment_is_exactly_pinned() -> None:
    """Refuse to compare pixels when any renderer input has drifted."""
    verify_visual_environment()


@pytest.mark.parametrize("case_name", CASES)
def test_visual_baseline(case_name: str) -> None:
    """Render each case and retain actual and amplified diff images on failure."""
    _RESULTS.mkdir(parents=True, exist_ok=True)
    expected = _BASELINES / f"{case_name}.png"
    actual = _RESULTS / f"{case_name}.actual.png"
    diff = _RESULTS / f"{case_name}.actual-failed-diff.png"
    actual.unlink(missing_ok=True)
    diff.unlink(missing_ok=True)

    if not expected.exists():
        pytest.fail(
            f"missing visual baseline {expected}; run `make visual-update` and review it"
        )

    figure = CASES[case_name]()
    try:
        write_png(figure, actual)
    finally:
        plt.close(figure)

    mismatch = compare_images(str(expected), str(actual), tol=_TOLERANCE)
    assert mismatch is None, mismatch
