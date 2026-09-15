"""Print the direct compatibility versions used by a CI environment."""

from __future__ import annotations

import platform

import matplotlib
import numpy as np
import pandas as pd


def main() -> None:
    """Report runtime and direct dependency versions on one stable line."""
    print(
        f"Python={platform.python_version()} "
        f"Matplotlib={matplotlib.__version__} "
        f"NumPy={np.__version__} pandas={pd.__version__}"
    )


if __name__ == "__main__":
    main()
