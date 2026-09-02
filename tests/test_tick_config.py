import pandas as pd
import pytest

from ggstyle._tick_config import resolve_tick_configuration


def test_minor_only_request_preserves_major_and_explicit_ticks() -> None:
    explicit = pd.DatetimeIndex(["2024-01-01", "2024-02-01"])

    result = resolve_tick_configuration(
        current_major="existing-major",
        current_minor="auto",
        current_explicit=explicit,
        minor=False,
    )

    assert result.major_spec == "existing-major"
    assert result.minor_spec is None
    assert result.explicit_ticks is explicit


@pytest.mark.parametrize("count", [True, 0, -1])
def test_count_request_requires_a_positive_integer(count: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        resolve_tick_configuration(
            current_major=None,
            current_minor="auto",
            current_explicit=None,
            n=count,
        )


def test_major_requests_are_mutually_exclusive() -> None:
    with pytest.raises(TypeError, match="only one"):
        resolve_tick_configuration(
            current_major=None,
            current_minor="auto",
            current_explicit=None,
            spec="monthly",
            every="2M",
        )
