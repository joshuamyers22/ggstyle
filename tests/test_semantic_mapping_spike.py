"""Regression tests for the v0.5 semantic-mapping architecture decision."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tools.semantic_mapping_spike import (
    CANDIDATES,
    CRITERIA,
    _native_line_prototype,
    _sample_data,
    probe_native,
    scorecard,
    validate_scorecard,
)


def test_scorecard_selects_one_narrow_native_direction() -> None:
    validate_scorecard()
    payload = scorecard()

    assert payload["decision"] == "narrow native helpers"
    assert payload["criteria"] == list(CRITERIA)
    assert [candidate["key"] for candidate in payload["candidates"]] == [
        "native",
        "seaborn-objects",
        "plotnine-docs",
    ]
    assert [candidate["total"] for candidate in payload["candidates"]] == [40, 30, 29]
    assert payload["hard_gates"] == {
        "date correctness": 4,
        "existing-axes support": 4,
    }


def test_every_candidate_has_complete_bounded_evidence() -> None:
    for candidate in CANDIDATES:
        assert [score.criterion for score in candidate.scores] == list(CRITERIA)
        assert all(1 <= score.value <= 5 for score in candidate.scores)
        assert all(score.evidence.endswith(".") for score in candidate.scores)
        assert all(source.startswith("https://") for source in candidate.sources)


def test_scorecard_is_strict_deterministic_json() -> None:
    first = json.dumps(scorecard(), allow_nan=False, indent=2, sort_keys=True)
    second = json.dumps(scorecard(), allow_nan=False, indent=2, sort_keys=True)

    assert first == second
    assert json.loads(first)["candidates"][0]["disposition"] == "selected"


def test_native_probe_preserves_axes_data_and_artists() -> None:
    result = probe_native()

    assert result.verified
    assert result.observations == {
        "adopts_existing_axes": True,
        "collapsed_date_scale": True,
        "mapped_groups": 2,
        "ordinary_line_artists": True,
        "preserves_input": True,
        "returns_artists": True,
        "separates_fixed_style": True,
    }


def test_native_prototype_rejects_ambiguous_mapped_and_fixed_color() -> None:
    data = _sample_data()
    figure, ax = plt.subplots()
    try:
        with pytest.raises(ValueError, match="both mapped and fixed"):
            _native_line_prototype(
                data,
                x="date",
                y="value",
                color="series",
                style={"color": "black"},
                ax=ax,
            )
        assert len(ax.lines) == 0
    finally:
        plt.close(figure)


def test_native_prototype_validates_columns_before_drawing() -> None:
    data = pd.DataFrame({"date": ["2024-01-01"], "value": [1.0]})
    figure, ax = plt.subplots()
    try:
        with pytest.raises(ValueError, match="unknown mapped columns: missing"):
            _native_line_prototype(data, x="date", y="missing", ax=ax)
        assert len(ax.lines) == 0
    finally:
        plt.close(figure)


def test_spike_does_not_add_optional_compilers_to_package_dependencies() -> None:
    pyproject = Path("pyproject.toml").read_text()

    dependencies = pyproject.split("[project.optional-dependencies]", maxsplit=1)[0]
    assert '"seaborn' not in dependencies
    assert '"plotnine' not in dependencies
