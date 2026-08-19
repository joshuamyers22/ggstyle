"""Sphinx configuration for the ggstyle documentation."""

from __future__ import annotations

from importlib.metadata import version as metadata_version

project = "ggstyle"
author = "Joshua Myers"
copyright = "2026, Joshua Myers"
release = metadata_version("ggstyle")

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.viewcode",
    "numpydoc",
]

autodoc_typehints = "none"
numpydoc_class_members_toctree = False
numpydoc_show_class_members = False
numpydoc_xref_param_type = False

doctest_global_setup = """
from ggstyle import Cadence, available_themes, dates, use_theme
"""
doctest_global_cleanup = """
import matplotlib.pyplot as plt
plt.close("all")
"""

html_theme = "pydata_sphinx_theme"
html_title = f"ggstyle {release}"
html_theme_options = {
    "github_url": "https://github.com/joshuamyers22/ggstyle",
    "show_toc_level": 2,
}

exclude_patterns = ["_build", "generated"]
