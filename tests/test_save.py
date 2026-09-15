"""Tests for deterministic, overwrite-safe figure export."""

from __future__ import annotations

import os
import struct
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


def _png_dimensions(path: Path) -> tuple[int, int]:
    contents = path.read_bytes()
    assert contents.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", contents[16:24])


def test_save_writes_exact_standard_canvas_and_restores_figure(tmp_path: Path) -> None:
    figure, ax = plt.subplots(figsize=(5, 3), dpi=72)
    ax.plot([0, 1], [0, 1])
    destination = tmp_path / "report.png"
    before_size = tuple(figure.get_size_inches())
    before_dpi = figure.dpi
    before_params = matplotlib.rcParams.copy()
    try:
        result = gs.save(
            figure,
            destination,
            width=2,
            height=1,
            dpi=100,
            bbox="standard",
            metadata={"Creator": "ggstyle"},
        )

        assert result == destination
        assert _png_dimensions(destination) == (200, 100)
        assert b"Creator" in destination.read_bytes()
        assert tuple(figure.get_size_inches()) == pytest.approx(before_size)
        assert figure.dpi == before_dpi
        assert matplotlib.rcParams == before_params
    finally:
        plt.close(figure)


def test_svg_output_is_byte_reproducible_and_has_no_timestamp(tmp_path: Path) -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [1, 0])
    first = tmp_path / "first.svg"
    second = tmp_path / "second.svg"
    try:
        gs.save(
            figure,
            first,
            width=2.54,
            height=1.27,
            units="cm",
            bbox="standard",
            metadata={"Creator": "ggstyle"},
        )
        gs.save(
            figure,
            second,
            width=25.4,
            height=12.7,
            units="mm",
            bbox="standard",
            metadata={"Creator": "ggstyle"},
        )

        contents = first.read_text()
        assert first.read_bytes() == second.read_bytes()
        assert 'width="72pt"' in contents
        assert 'height="36pt"' in contents
        assert "ggstyle" in contents
        assert "dc:date" not in contents
    finally:
        plt.close(figure)


def test_pdf_suppresses_variable_timestamp_metadata(tmp_path: Path) -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    destination = tmp_path / "report.pdf"
    repeated = tmp_path / "repeated.pdf"
    try:
        gs.save(figure, destination, width=2, height=1, bbox="standard")
        gs.save(figure, repeated, width=2, height=1, bbox="standard")

        contents = destination.read_bytes()
        assert contents == repeated.read_bytes()
        assert contents.startswith(b"%PDF")
        assert b"/CreationDate" not in contents
        assert b"/ModDate" not in contents
    finally:
        plt.close(figure)


@pytest.mark.parametrize(
    ("units", "width", "height", "dpi", "expected"),
    [
        ("in", 2.0, 1.0, 100.0, (2.0, 1.0)),
        ("cm", 2.54, 5.08, 100.0, (1.0, 2.0)),
        ("mm", 25.4, 50.8, 100.0, (1.0, 2.0)),
        ("px", 640.0, 480.0, 160.0, (4.0, 3.0)),
    ],
)
def test_units_are_converted_before_rendering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    units: str,
    width: float,
    height: float,
    dpi: float,
    expected: tuple[float, float],
) -> None:
    figure, _ = plt.subplots(figsize=(5, 3))
    seen: list[tuple[tuple[float, float], dict[str, object]]] = []

    def fake_savefig(filename: Path, **options: object) -> None:
        seen.append((tuple(figure.get_size_inches()), options))
        Path(filename).write_bytes(b"artifact")

    monkeypatch.setattr(figure, "savefig", fake_savefig)
    destination = tmp_path / "report.png"
    try:
        gs.save(
            figure,
            destination,
            width=width,
            height=height,
            units=units,
            dpi=dpi,
            transparent=True,
        )

        assert seen[0][0] == pytest.approx(expected)
        assert seen[0][1]["dpi"] == dpi
        assert seen[0][1]["format"] == "png"
        assert seen[0][1]["transparent"] is True
        assert seen[0][1]["bbox_inches"] == "tight"
        assert seen[0][1]["pad_inches"] == 0.1
        assert tuple(figure.get_size_inches()) == pytest.approx((5, 3))
    finally:
        plt.close(figure)


def test_explicit_format_supports_a_destination_without_suffix(tmp_path: Path) -> None:
    figure, _ = plt.subplots()
    destination = tmp_path / "artifact"
    try:
        gs.save(figure, destination, width=1, height=1, format=".PNG")
        assert _png_dimensions(destination)[0] > 0
    finally:
        plt.close(figure)


def test_equivalent_format_alias_matches_filename_extension(tmp_path: Path) -> None:
    figure, _ = plt.subplots()
    destination = tmp_path / "artifact.jpg"
    try:
        gs.save(
            figure,
            destination,
            width=1,
            height=1,
            format="jpeg",
            bbox="standard",
        )
        assert destination.read_bytes().startswith(b"\xff\xd8")
    finally:
        plt.close(figure)


def test_existing_destination_is_rejected_before_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "report.png"
    destination.write_bytes(b"original")
    figure, _ = plt.subplots()
    called = False

    def fail_if_called(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(figure, "savefig", fail_if_called)
    try:
        with pytest.raises(FileExistsError, match="overwrite=True"):
            gs.save(figure, destination, width=2, height=1)
        assert not called
        assert destination.read_bytes() == b"original"
    finally:
        plt.close(figure)


def test_overwrite_replaces_an_existing_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "report.png"
    destination.write_bytes(b"original")
    destination.chmod(0o640)
    figure, _ = plt.subplots()
    try:
        gs.save(
            figure,
            destination,
            width=1,
            height=1,
            bbox="standard",
            overwrite=True,
        )
        assert destination.read_bytes() != b"original"
        assert _png_dimensions(destination) == (300, 300)
        if os.name != "nt":
            assert destination.stat().st_mode & 0o777 == 0o640
    finally:
        plt.close(figure)


def test_renderer_failure_preserves_existing_destination_and_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "report.png"
    destination.write_bytes(b"original")
    figure, _ = plt.subplots(figsize=(5, 3))

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected renderer failure")

    monkeypatch.setattr(figure, "savefig", fail)
    try:
        with pytest.raises(RuntimeError, match="injected renderer"):
            gs.save(
                figure,
                destination,
                width=2,
                height=1,
                overwrite=True,
            )
        assert destination.read_bytes() == b"original"
        assert tuple(figure.get_size_inches()) == pytest.approx((5, 3))
        assert list(tmp_path.glob(".report.png.*.tmp")) == []
    finally:
        plt.close(figure)


def test_empty_renderer_output_is_never_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "report.png"
    figure, _ = plt.subplots()

    def leave_empty(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(figure, "savefig", leave_empty)
    try:
        with pytest.raises(RuntimeError, match="empty export"):
            gs.save(figure, destination, width=2, height=1)
        assert not destination.exists()
        assert list(tmp_path.glob(".report.png.*.tmp")) == []
    finally:
        plt.close(figure)


def test_metadata_is_defensively_copied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "report.png"
    provided = {"Creator": "caller"}
    figure, _ = plt.subplots()

    def mutate_received_metadata(filename: Path, **options: object) -> None:
        received = options["metadata"]
        assert isinstance(received, dict)
        received["Creator"] = "renderer"
        Path(filename).write_bytes(b"artifact")

    monkeypatch.setattr(figure, "savefig", mutate_received_metadata)
    try:
        gs.save(
            figure,
            destination,
            width=2,
            height=1,
            metadata=provided,
        )
        assert provided == {"Creator": "caller"}
    finally:
        plt.close(figure)


@pytest.mark.parametrize("name", ["width", "height", "dpi"])
@pytest.mark.parametrize("value", [True, "2", object()])
def test_numeric_options_require_real_numbers(name: str, value: object) -> None:
    figure, _ = plt.subplots()
    options = {"width": 2, "height": 1, "dpi": 100, name: value}
    try:
        with pytest.raises(TypeError, match=name):
            gs.save(figure, "report.png", **options)
    finally:
        plt.close(figure)


@pytest.mark.parametrize("name", ["width", "height", "dpi"])
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_numeric_options_must_be_finite_and_positive(name: str, value: float) -> None:
    figure, _ = plt.subplots()
    options = {"width": 2, "height": 1, "dpi": 100, name: value}
    try:
        with pytest.raises(ValueError, match=name):
            gs.save(figure, "report.png", **options)
    finally:
        plt.close(figure)


@pytest.mark.parametrize(
    ("option", "value", "error"),
    [
        ("units", None, TypeError),
        ("units", "pt", ValueError),
        ("bbox", None, TypeError),
        ("bbox", "crop", ValueError),
        ("transparent", 1, TypeError),
        ("overwrite", 1, TypeError),
        ("format", 1, TypeError),
        ("format", "", ValueError),
        ("metadata", [], TypeError),
        ("metadata", {1: "value"}, TypeError),
        ("metadata", {"": "value"}, ValueError),
        ("metadata", {"Creator": 1}, TypeError),
    ],
)
def test_invalid_export_policies_fail_before_writing(
    option: str, value: object, error: type[Exception]
) -> None:
    figure, _ = plt.subplots()
    options = {"width": 2, "height": 1, option: value}
    try:
        with pytest.raises(error):
            gs.save(figure, "report.png", **options)
    finally:
        plt.close(figure)


def test_invalid_figure_and_filename_are_rejected() -> None:
    with pytest.raises(TypeError, match="matplotlib Figure"):
        gs.save(object(), "report.png", width=2, height=1)

    figure, _ = plt.subplots()
    try:
        for filename in (object(), b"report.png"):
            with pytest.raises(TypeError, match="filename"):
                gs.save(figure, filename, width=2, height=1)
        for filename in ("", "output/"):
            with pytest.raises(ValueError, match="identify a file"):
                gs.save(figure, filename, width=2, height=1)
    finally:
        plt.close(figure)


def test_format_requires_a_suffix_or_explicit_value(tmp_path: Path) -> None:
    figure, _ = plt.subplots()
    try:
        with pytest.raises(ValueError, match="format is required"):
            gs.save(figure, tmp_path / "artifact", width=2, height=1)
        with pytest.raises(ValueError, match="unsupported format"):
            gs.save(figure, tmp_path / "artifact.unknown", width=2, height=1)
        with pytest.raises(ValueError, match="does not match"):
            gs.save(
                figure,
                tmp_path / "artifact.svg",
                width=2,
                height=1,
                format="png",
            )
    finally:
        plt.close(figure)


def test_destination_parent_must_be_an_existing_directory(tmp_path: Path) -> None:
    figure, _ = plt.subplots()
    regular_file = tmp_path / "parent"
    regular_file.write_text("not a directory")
    try:
        with pytest.raises(FileNotFoundError, match="parent does not exist"):
            gs.save(
                figure,
                tmp_path / "missing" / "report.png",
                width=2,
                height=1,
            )
        with pytest.raises(NotADirectoryError, match="not a directory"):
            gs.save(figure, regular_file / "report.png", width=2, height=1)
        with pytest.raises(IsADirectoryError, match="is a directory"):
            gs.save(figure, tmp_path, width=2, height=1, format="png")
    finally:
        plt.close(figure)
