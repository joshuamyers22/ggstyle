"""Owned observation provenance for one or more date-axis handles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from weakref import WeakKeyDictionary, WeakSet

import matplotlib.collections as mcollections
import numpy as np
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection, PolyCollection
from matplotlib.path import Path

from . import _axis_data


class DateDiscoveryError(TypeError):
    """Raised when an artist's date coordinates cannot be discovered safely."""


@dataclass(frozen=True)
class RegistryCandidate:
    """Prepared observation state that has not yet been committed."""

    members: tuple[Any, ...]
    numbers: np.ndarray
    missing_values: int
    trusted: bool
    artist_values: tuple[tuple[Artist, np.ndarray], ...]
    local_numbers: tuple[np.ndarray, ...]


@dataclass(frozen=True)
class RegistrySnapshot:
    """Restorable registry state used by transactional refresh."""

    numbers: np.ndarray
    missing_values: int
    trusted: bool
    revision: int
    artist_values: tuple[tuple[Artist, np.ndarray], ...]


class ObservationRegistry:
    """Revisioned observation union shared weakly by live handles."""

    def __init__(self) -> None:
        self._members: WeakSet[Any] = WeakSet()
        self._artist_values: WeakKeyDictionary[Artist, np.ndarray] = WeakKeyDictionary()
        self._numbers = _immutable(np.empty(0, dtype=float))
        self._missing_values = 0
        self._trusted = False
        self._revision = 0

    @property
    def members(self) -> tuple[Any, ...]:
        """Return a stable snapshot of currently live member handles."""
        return tuple(sorted(self._members, key=id))

    @property
    def numbers(self) -> np.ndarray:
        """Return the immutable effective observation union."""
        return self._numbers

    @property
    def missing_values(self) -> int:
        return self._missing_values

    @property
    def trusted(self) -> bool:
        return self._trusted

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def artist_values(self) -> WeakKeyDictionary[Artist, np.ndarray]:
        """Return weak provenance state for supported source artists."""
        return self._artist_values

    def attach(self, handle: Any) -> None:
        """Attach a handle without taking ownership of its lifetime."""
        self._members.add(handle)

    def detach(self, handle: Any) -> None:
        """Detach a handle if it is still a member."""
        self._members.discard(handle)

    def prepare(self) -> RegistryCandidate:
        """Discover and validate a complete candidate without mutating registry state."""
        members = self.members
        all_batches: list[np.ndarray] = []
        artist_values: list[tuple[Artist, np.ndarray]] = []
        local_numbers: list[np.ndarray] = []
        missing_values = 0
        trusted = False

        for handle in members:
            explicit = handle._explicit_data
            discovery = _discover(
                handle.ax,
                handle._managed_artists(),
                explicit.numbers,
            )
            batches = [explicit.numbers]
            batches.extend(values for _, values in discovery.artist_values)
            local = _union(batches)
            local_state = _axis_data.AxisData(
                local,
                explicit.missing_values,
                explicit.trusted,
            )
            _axis_data.validate(handle.ax, local_state)

            local_numbers.append(local)
            all_batches.append(local)
            artist_values.extend(discovery.artist_values)
            missing_values += local_state.missing_values
            trusted = trusted or explicit.trusted

        return RegistryCandidate(
            members,
            _union(all_batches),
            missing_values,
            trusted,
            tuple(artist_values),
            tuple(local_numbers),
        )

    def commit(self, candidate: RegistryCandidate) -> None:
        """Publish a fully prepared candidate as one new revision."""
        self._numbers = _immutable(candidate.numbers)
        self._missing_values = candidate.missing_values
        self._trusted = candidate.trusted
        self._artist_values = WeakKeyDictionary(candidate.artist_values)
        self._revision += 1

    def snapshot(self) -> RegistrySnapshot:
        """Capture current state for rollback."""
        return RegistrySnapshot(
            self._numbers,
            self._missing_values,
            self._trusted,
            self._revision,
            tuple(self._artist_values.items()),
        )

    def restore(self, snapshot: RegistrySnapshot) -> None:
        """Restore a prior committed revision after a failed apply step."""
        self._numbers = snapshot.numbers
        self._missing_values = snapshot.missing_values
        self._trusted = snapshot.trusted
        self._revision = snapshot.revision
        self._artist_values = WeakKeyDictionary(snapshot.artist_values)


@dataclass(frozen=True)
class _Discovery:
    artist_values: tuple[tuple[Artist, np.ndarray], ...]


def _discover(
    ax: Axes,
    managed: set[Artist],
    explicit_numbers: np.ndarray,
) -> _Discovery:
    """Discover supported artist observations owned by one axes."""
    contributions: list[tuple[Artist, np.ndarray]] = []

    for line in ax.lines:
        if line in managed or line.get_transform() is ax.get_xaxis_transform():
            continue
        original = np.ma.asarray(line.get_xdata(orig=True))
        if line.get_transform() is not ax.transData:
            if _axis_data.has_date_converter(ax) and not _is_numeric(original):
                raise DateDiscoveryError(
                    f"cannot refresh {type(line).__name__} on this date axis: its x "
                    "transform is not ax.transData; use a data-space transform or "
                    "supply complete observations through dates(ax, data=...)"
                )
            continue
        if (
            _axis_data.has_date_converter(ax)
            and _is_numeric(original)
            and not _covered_by_explicit(original, explicit_numbers)
        ):
            raise DateDiscoveryError(
                "cannot infer whether numeric Line2D x values are matplotlib date "
                "numbers; pass their complete dates through dates(ax, data=...)"
            )
        values = np.ma.asarray(line.get_xdata(orig=False), dtype=float)
        numbers, _ = _finite_unmasked(values)
        if numbers.size:
            contributions.append((line, numbers))

    for collection in ax.collections:
        if collection in managed:
            continue
        if isinstance(collection, PathCollection):
            offsets = np.ma.asarray(collection.get_offsets(), dtype=float)
            if offsets.size == 0:
                continue
            if collection.get_offset_transform() is not ax.transData:
                if _axis_data.has_date_converter(ax):
                    raise DateDiscoveryError(
                        f"cannot refresh {type(collection).__name__} on this date "
                        "axis: its offsets do not use ax.transData; use a data-space "
                        "transform or supply complete observations through "
                        "dates(ax, data=...)"
                    )
                continue
            numbers, _ = _finite_unmasked(offsets[:, 0])
            if numbers.size:
                contributions.append((collection, numbers))
            continue

        if isinstance(collection, PolyCollection):
            numbers = _polygon_observations(ax, collection, explicit_numbers)
            if numbers.size:
                contributions.append((collection, numbers))
            continue

        if (
            _axis_data.has_date_converter(ax)
            and collection.get_transform() is ax.transData
            and collection.get_paths()
        ):
            raise DateDiscoveryError(
                f"cannot discover observation dates from "
                f"{type(collection).__name__}; pass the complete dates through "
                "dates(ax, data=...) or remove the unsupported collection"
            )

    return _Discovery(tuple(contributions))


def _polygon_observations(
    ax: Axes,
    collection: PolyCollection,
    explicit_numbers: np.ndarray,
) -> np.ndarray:
    """Recover source x vertices from a native fill-between collection."""
    direction = getattr(collection, "t_direction", None)
    if direction == "y" or (
        direction is None and _axis_data.axis_has_date_converter(ax.yaxis)
    ):
        raise DateDiscoveryError(
            "fill_betweenx is unsupported on an x-date handle because its dates "
            "belong to the y axis"
        )

    paths = collection.get_paths()
    if not paths:
        return _immutable(np.empty(0, dtype=float))
    if collection.get_transform() is not ax.transData:
        raise DateDiscoveryError(
            f"cannot refresh {type(collection).__name__} on this date axis: its "
            "vertices do not use ax.transData; use a data-space transform"
        )

    fill_between_type = getattr(mcollections, "FillBetweenPolyCollection", None)
    if fill_between_type is not None and not isinstance(collection, fill_between_type):
        raise DateDiscoveryError(
            f"cannot discover observation dates from {type(collection).__name__}; "
            "only native fill_between polygon collections are supported"
        )

    batches: list[np.ndarray] = []
    for path in paths:
        try:
            source = _fill_between_source_x(path)
        except ValueError as error:
            if explicit_numbers.size:
                return _immutable(np.empty(0, dtype=float))
            raise DateDiscoveryError(
                "cannot recover fill_between observation dates from its polygon "
                "topology; pass the complete dates through dates(ax, data=...)"
            ) from error
        if _looks_like_midpoint_step(source):
            return _explicit_or_raise_midpoint_step(explicit_numbers)
        numbers, _ = _finite_unmasked(np.ma.asarray(source, dtype=float))
        if numbers.size:
            batches.append(numbers)
    return _union(batches)


def _fill_between_source_x(path: Path) -> np.ndarray:
    """Return one path's source-side x sequence, excluding synthetic endpoints."""
    vertices = np.asarray(path.vertices, dtype=float)
    raw_codes = path.codes
    if vertices.ndim != 2 or vertices.shape[1] != 2:
        raise ValueError("polygon vertices are not a two-column array")
    if raw_codes is None:
        raise ValueError("polygon has no matching path codes")
    codes = np.asarray(raw_codes, dtype=np.uint8)
    if len(codes) != len(vertices):
        raise ValueError("polygon has no matching path codes")
    if len(vertices) < 5 or codes[0] != Path.MOVETO or codes[-1] != Path.CLOSEPOLY:
        raise ValueError("polygon is not a closed fill_between path")

    body = vertices[:-1]
    if (len(body) - 2) % 2:
        raise ValueError("polygon sides have unequal lengths")
    side_length = (len(body) - 2) // 2
    if side_length < 1:
        raise ValueError("polygon has no source vertices")
    source = body[1 : side_length + 1, 0]
    reverse_side = body[side_length + 2 :, 0]
    if not np.array_equal(source, reverse_side[::-1], equal_nan=True):
        raise ValueError("polygon sides do not share a fill_between x sequence")
    return source


def _looks_like_midpoint_step(values: np.ndarray) -> bool:
    """Recognize the unrecoverable midpoint-step topology used before Matplotlib 3.9."""
    if len(values) < 4 or len(values) % 2:
        return False
    interior = values[1:-1]
    return bool(np.all(interior[::2] == interior[1::2]))


def _explicit_or_raise_midpoint_step(explicit_numbers: np.ndarray) -> np.ndarray:
    if explicit_numbers.size:
        return _immutable(np.empty(0, dtype=float))
    raise DateDiscoveryError(
        "cannot recover original dates from fill_between(step='mid') because "
        "Matplotlib retains midpoint vertices instead; pass the complete dates "
        "through dates(ax, data=...)"
    )


def _finite_unmasked(values: np.ma.MaskedArray) -> tuple[np.ndarray, int]:
    data = np.asarray(np.ma.getdata(values), dtype=float).reshape(-1)
    mask = np.ma.getmaskarray(values).reshape(-1)
    valid = ~mask & np.isfinite(data)
    return _immutable(data[valid]), int(np.count_nonzero(~valid))


def _is_numeric(values: np.ma.MaskedArray) -> bool:
    return np.issubdtype(values.dtype, np.number)


def _covered_by_explicit(
    values: np.ma.MaskedArray,
    explicit_numbers: np.ndarray,
) -> bool:
    numbers, _ = _finite_unmasked(np.ma.asarray(values, dtype=float))
    if numbers.size == 0:
        return True
    if explicit_numbers.size == 0:
        return False
    indexes = np.searchsorted(explicit_numbers, numbers)
    indexes = np.clip(indexes, 0, explicit_numbers.size - 1)
    return bool(np.all(np.isclose(explicit_numbers[indexes], numbers)))


def _union(batches: list[np.ndarray]) -> np.ndarray:
    nonempty = [
        np.asarray(values, dtype=float).reshape(-1)
        for values in batches
        if values.size
    ]
    if not nonempty:
        return _immutable(np.empty(0, dtype=float))
    values = np.concatenate(nonempty)
    return _immutable(np.unique(values[np.isfinite(values)]))


def _immutable(values: np.ndarray) -> np.ndarray:
    result = np.array(values, dtype=float, copy=True)
    result.setflags(write=False)
    return result
