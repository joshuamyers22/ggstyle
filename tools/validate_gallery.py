"""Execute every published gallery builder and validate its raster artifacts."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "examples"))

from finishing_gallery import render  # noqa: E402
from semantic_gallery import render as render_semantic  # noqa: E402

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _validate(path: Path) -> None:
    contents = path.read_bytes()
    if not contents.startswith(_PNG_SIGNATURE):
        raise RuntimeError(f"gallery builder did not produce a PNG: {path}")
    if len(contents) < 10_000:
        raise RuntimeError(f"gallery artifact is unexpectedly small: {path}")


def main() -> int:
    """Render to a temporary directory by default, or refresh reviewed assets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="replace the reviewed images in examples instead of checking temporary output",
    )
    arguments = parser.parse_args()
    if arguments.write:
        paths = (*render(_ROOT / "examples"), *render_semantic(_ROOT / "examples"))
        for path in paths:
            _validate(path)
            print(path.relative_to(_ROOT))
        return 0

    with tempfile.TemporaryDirectory(prefix="ggstyle-gallery-") as directory:
        paths = (*render(Path(directory)), *render_semantic(Path(directory)))
        for path in paths:
            _validate(path)
    print(f"gallery validation: {len(paths)} executable figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
