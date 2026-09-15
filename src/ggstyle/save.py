"""Deterministic, overwrite-safe figure export."""

from __future__ import annotations

import math
import os
import secrets
import stat
from collections.abc import Mapping
from numbers import Real
from pathlib import Path
from typing import Any, Literal, TypeAlias, cast

import matplotlib as mpl
from matplotlib.figure import Figure

__all__ = ["save"]

Unit: TypeAlias = Literal["in", "cm", "mm", "px"]
BoundingPolicy: TypeAlias = Literal["tight", "standard"]

_INCHES_PER_UNIT: dict[str, float] = {
    "in": 1.0,
    "cm": 1.0 / 2.54,
    "mm": 1.0 / 25.4,
}
_FORMAT_ALIASES = {
    "jpg": "jpeg",
    "tif": "tiff",
}


def _positive_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a positive real number, got {value!r}")
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(f"{name} must be finite and positive, got {value!r}")
    return resolved


def _destination(filename: object) -> Path:
    if not isinstance(filename, (str, os.PathLike)):
        raise TypeError(f"filename must be a string or path-like object, got {filename!r}")
    raw = os.fspath(filename)
    if not isinstance(raw, str):
        raise TypeError(f"filename must resolve to text, got {raw!r}")
    if not raw.strip() or raw.endswith(os.sep) or (
        os.altsep is not None and raw.endswith(os.altsep)
    ):
        raise ValueError(f"filename must identify a file, got {raw!r}")
    return Path(raw)


def _normalized_format(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"format must be a string or None, got {value!r}")
    resolved = value.removeprefix(".").strip().lower()
    if not resolved:
        raise ValueError("format must be a non-empty string")
    return resolved


def _format(figure: Figure, destination: Path, requested: str | None) -> str:
    supported = tuple(sorted(figure.canvas.get_supported_filetypes()))
    suffix = destination.suffix.removeprefix(".").lower()
    resolved = _normalized_format(requested) if requested is not None else suffix
    if not resolved:
        raise ValueError("format is required when filename has no extension")
    if resolved not in supported:
        raise ValueError(
            f"unsupported format {resolved!r}; supported formats are {list(supported)}"
        )
    if suffix and _FORMAT_ALIASES.get(suffix, suffix) != _FORMAT_ALIASES.get(
        resolved, resolved
    ):
        raise ValueError(
            f"filename extension {suffix!r} does not match format {resolved!r}"
        )
    return resolved


def _metadata(value: object, output_format: str) -> dict[str, str | None]:
    if value is None:
        provided: dict[str, str | None] = {}
    elif not isinstance(value, Mapping):
        raise TypeError(f"metadata must be a mapping or None, got {value!r}")
    else:
        provided = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"metadata keys must be strings, got {key!r}")
            if not key:
                raise ValueError("metadata keys must be non-empty strings")
            if item is not None and not isinstance(item, str):
                raise TypeError(
                    f"metadata value for {key!r} must be a string or None, got {item!r}"
                )
            provided[key] = item

    deterministic: dict[str, str | None] = {}
    canonical = _FORMAT_ALIASES.get(output_format, output_format)
    if canonical == "svg":
        deterministic["Date"] = None
    elif canonical == "pdf":
        deterministic.update({"CreationDate": None, "ModDate": None})
    deterministic.update(provided)
    return deterministic


def _size_inches(
    width: float, height: float, units: Unit, dpi: float
) -> tuple[float, float]:
    if units == "px":
        return width / dpi, height / dpi
    factor = _INCHES_PER_UNIT[units]
    return width * factor, height * factor


def _temporary_path(destination: Path) -> Path:
    for _ in range(100):  # pragma: no branch - collisions are exceptionally unlikely
        candidate = destination.parent / (
            f".{destination.name}.{secrets.token_hex(8)}.tmp"
        )
        try:
            with candidate.open("xb"):
                pass
        except FileExistsError:  # pragma: no cover - cryptographic-name collision
            continue
        return candidate
    raise FileExistsError("could not reserve a temporary export path")  # pragma: no cover


def _existing_mode(destination: Path) -> int | None:
    try:
        mode = destination.lstat().st_mode
    except FileNotFoundError:
        return None
    return stat.S_IMODE(mode) if stat.S_ISREG(mode) else None


def _publish(temporary: Path, destination: Path, *, overwrite: bool) -> None:
    if overwrite:
        mode = _existing_mode(destination)
        if mode is not None:
            temporary.chmod(mode)
        os.replace(temporary, destination)
        return
    try:
        os.link(temporary, destination)
    except FileExistsError as error:
        raise FileExistsError(
            f"destination already exists: {destination}; pass overwrite=True to replace it"
        ) from error


def save(
    figure: Figure,
    filename: str | os.PathLike[str],
    *,
    width: float,
    height: float,
    units: Unit = "in",
    dpi: float = 300,
    format: str | None = None,
    transparent: bool = False,
    bbox: BoundingPolicy = "tight",
    metadata: Mapping[str, str | None] | None = None,
    overwrite: bool = False,
) -> Path:
    """
    Save an explicit Matplotlib figure with reproducible, safe defaults.

    Parameters
    ----------
    figure : matplotlib.figure.Figure
        Figure to export. A current figure is never inferred.
    filename : str or path-like
        Exact destination. Parent directories are not created automatically.
    width : float
        Positive output-canvas width in ``units``.
    height : float
        Positive output-canvas height in ``units``.
    units : {"in", "cm", "mm", "px"}, default "in"
        Unit for ``width`` and ``height``. Pixel dimensions use ``dpi`` for conversion.
    dpi : float, default 300
        Positive rendering resolution. This also defines the physical size of pixel
        dimensions for vector output.
    format : str or None, optional
        Matplotlib output format. ``None`` infers it from the filename extension. An
        explicit format must agree with any extension.
    transparent : bool, default False
        Whether figure and axes patches are transparent in the saved artifact.
    bbox : {"tight", "standard"}, default "tight"
        ``"tight"`` crops to decorated content with deterministic 0.1-inch padding;
        ``"standard"`` preserves the complete requested canvas.
    metadata : mapping or None, optional
        Format-specific string metadata passed to Matplotlib. ``None`` values suppress
        supported backend defaults. SVG and PDF timestamps are suppressed by default.
    overwrite : bool, default False
        Replace an existing file only when explicitly true.

    Returns
    -------
    pathlib.Path
        The destination path after a successful atomic publication.

    Raises
    ------
    TypeError
        If an argument has the wrong type.
    ValueError
        If dimensions, format, units, bounding policy, or metadata are invalid.
    FileExistsError
        If the destination exists and ``overwrite`` is false.
    FileNotFoundError
        If the destination parent does not exist.

    Notes
    -----
    Rendering occurs in a temporary file in the destination directory. A failed render
    leaves an existing destination intact and never publishes a partial new artifact.
    The original figure size and global ``rcParams`` are restored before publication.
    SVG IDs use a stable salt and SVG/PDF timestamps are omitted for repeatable output.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> _ = ax.plot([0, 1], [0, 1])
    >>> path = save(fig, "report.png", width=7, height=4, overwrite=True)
    >>> path.name
    'report.png'
    >>> path.unlink()
    >>> plt.close(fig)
    """
    if not isinstance(figure, Figure):
        raise TypeError(f"figure must be a matplotlib Figure, got {figure!r}")
    destination = _destination(filename)
    resolved_width = _positive_number("width", width)
    resolved_height = _positive_number("height", height)
    resolved_dpi = _positive_number("dpi", dpi)
    if not isinstance(units, str):
        raise TypeError(f"units must be a string, got {units!r}")
    if units not in (*_INCHES_PER_UNIT, "px"):
        raise ValueError(
            f"units must be one of {[*_INCHES_PER_UNIT, 'px']}, got {units!r}"
        )
    if not isinstance(transparent, bool):
        raise TypeError(f"transparent must be a bool, got {transparent!r}")
    if not isinstance(bbox, str):
        raise TypeError(f"bbox must be a string, got {bbox!r}")
    if bbox not in ("tight", "standard"):
        raise ValueError(f"bbox must be 'tight' or 'standard', got {bbox!r}")
    if not isinstance(overwrite, bool):
        raise TypeError(f"overwrite must be a bool, got {overwrite!r}")
    output_format = _format(figure, destination, format)
    output_metadata = _metadata(metadata, output_format)

    if not destination.parent.exists():
        raise FileNotFoundError(
            f"destination parent does not exist: {destination.parent}"
        )
    if not destination.parent.is_dir():
        raise NotADirectoryError(
            f"destination parent is not a directory: {destination.parent}"
        )
    if destination.is_dir() and not destination.is_symlink():
        raise IsADirectoryError(f"destination is a directory: {destination}")
    if (destination.exists() or destination.is_symlink()) and not overwrite:
        raise FileExistsError(
            f"destination already exists: {destination}; pass overwrite=True to replace it"
        )

    size_inches = _size_inches(
        resolved_width, resolved_height, cast(Unit, units), resolved_dpi
    )
    current_size = figure.get_size_inches()
    original_size = (float(current_size[0]), float(current_size[1]))
    temporary = _temporary_path(destination)
    try:
        try:
            figure.set_size_inches(*size_inches, forward=False)
            with mpl.rc_context({"svg.hashsalt": "ggstyle"}):
                if bbox == "tight":
                    figure.savefig(
                        temporary,
                        dpi=resolved_dpi,
                        format=output_format,
                        transparent=transparent,
                        bbox_inches="tight",
                        pad_inches=0.1,
                        metadata=cast(Any, output_metadata or None),
                    )
                else:
                    figure.savefig(
                        temporary,
                        dpi=resolved_dpi,
                        format=output_format,
                        transparent=transparent,
                        bbox_inches=None,
                        metadata=cast(Any, output_metadata or None),
                    )
        finally:
            figure.set_size_inches(*original_size, forward=False)

        if temporary.stat().st_size == 0:
            raise RuntimeError("Matplotlib produced an empty export artifact")
        _publish(temporary, destination, overwrite=overwrite)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
