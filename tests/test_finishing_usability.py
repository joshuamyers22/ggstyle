"""Executable acceptance checks for the v0.4 finishing API decision."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from tools.finishing_usability import (
    CASES,
    MINIMUM_REDUCTION,
    REQUIRED_CAPABILITIES,
    TARGET_PERSONAS,
    build_report,
    logical_statement_count,
    validate_cases,
)


def test_registry_has_ten_unique_valid_cases() -> None:
    validate_cases()
    assert len(CASES) == 10
    assert len({case.case_id for case in CASES}) == 10


def test_fixtures_cover_every_target_persona_and_capability() -> None:
    assert {persona for case in CASES for persona in case.personas} == TARGET_PERSONAS
    assert {
        capability for case in CASES for capability in case.capabilities
    } == REQUIRED_CAPABILITIES


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_proposal_is_shorter_and_retains_native_objects(case) -> None:
    assert logical_statement_count(case.proposed) < logical_statement_count(case.baseline)
    assert "native-axes" in case.guarantees
    assert "no-data-mutation" in case.guarantees


def test_aggregate_reduction_exceeds_product_gate() -> None:
    report = build_report()
    assert report.reduction >= MINIMUM_REDUCTION
    assert report.baseline_statements == 40
    assert report.proposed_statements == 11


def test_fixture_models_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        CASES[0].title = "changed"  # type: ignore[misc]


def test_architecture_decision_traces_every_fixture() -> None:
    decision = Path("docs/architecture/0002-finishing-api.md").read_text()
    for case in CASES:
        assert case.case_id in decision


def test_fixture_policy_does_not_import_matplotlib() -> None:
    source = Path("tools/finishing_usability.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
