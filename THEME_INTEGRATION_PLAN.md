# ggplot2 theme integration plan

Status: core integration implemented; automated visual baselines remain follow-up

Reference baseline: ggplot2 4.0.3, checked 2026-09-13

## Objective

Add a recognizable matplotlib analogue for every complete theme exported by ggplot2,
without changing ggstyle's default theme, introducing import-time side effects, or
breaking the standalone `.mplstyle` workflow.

This is a semantic port, not a pixel-for-pixel reimplementation. The target is that the
panel, grid, axes, ticks, text, legend, and canvas make the same design choices as the
corresponding ggplot2 theme. Exact text metrics and layout will continue to depend on
matplotlib and the installed font stack.

Authoritative references:

- [ggplot2 complete-theme reference](https://ggplot2.tidyverse.org/reference/ggtheme.html)
- [ggplot2 4.0.3 theme source](https://github.com/tidyverse/ggplot2/blob/v4.0.3/R/theme-defaults.R)

## Theme inventory

ggplot2 4.0.3 exports nine distinct complete themes. It exposes ten function names
because `theme_gray()` is an alias of `theme_grey()`.

| ggplot2 API | ggstyle canonical name | Visual intent | Integration status |
|---|---|---|---|
| `theme_grey()` / `theme_gray()` | `grey` | Signature grey panel with white gridlines | Existing; preserved |
| `theme_bw()` | `bw` | White panel, dark border, light grey grid | Added |
| `theme_linedraw()` | `linedraw` | White panel using black lines of varying widths | Added |
| `theme_light()` | `light` | White panel with light grey border, grid, and ticks | Added |
| `theme_dark()` | `dark` | Mid-grey panel with subdued gridlines | Added |
| `theme_minimal()` | `minimal` | White/blank panel with gridlines but no border or ticks | Existing; preserved as default |
| `theme_classic()` | `classic` | White panel, left and bottom axis lines, no grid | Added |
| `theme_void()` | `void` | No axes, ticks, grid, or panel decoration | Added with a documented matplotlib limitation |
| `theme_test()` | `test` | Stable white, bordered, grid-free theme for visual tests | Added and documented as testing-oriented |

Third-party themes from extension packages such as `ggthemes` are not part of this
inventory. They should be considered separately after the built-in set is stable.

## Public API decisions

1. Keep `minimal` as `DEFAULT_THEME`. Adding parity themes must not change existing plot
   output unless the caller selects one.
2. Expose short, lowercase canonical names from `available_themes()` in this order:

   ```python
   [
       "minimal",
       "grey",
       "bw",
       "linedraw",
       "light",
       "dark",
       "classic",
       "void",
       "test",
   ]
   ```

3. Accept each ggplot2 spelling as an alias: `theme_minimal`, `theme_grey`,
   `theme_gray`, `theme_bw`, `theme_linedraw`, `theme_light`, `theme_dark`,
   `theme_classic`, `theme_void`, and `theme_test`. Continue accepting `gray`,
   `default`, and `ggstyle` as today.
4. Keep `test` public for completeness, but describe it as a reproducible baseline rather
   than a recommended presentation theme.
5. Initially port the default ggplot2 4.0.3 values only. Do not add `base_size`,
   `base_family`, `header_family`, `ink`, `paper`, or `accent` parameters to
   `use_theme()` in the same change. Parameterized theme generation is a separate API
   design problem and would remove the simplicity of returning a static stylesheet path.
6. Keep every distributed stylesheet complete and independently usable through
   `plt.style.use(gs.stylesheet(name))`. Runtime-only composition would break this
   existing guarantee.

## Visual mapping

The common ggstyle identity remains shared across the presentation themes: figure size,
DPI, type scale, font fallback list, line defaults, and the Okabe-Ito-derived colour
cycle. The theme variants change the non-data surface. Dark-theme cycle colours must be
checked for contrast; change only colours that fail the contrast and distinguishability
review, and document any divergence.

| Theme | Panel and canvas | Grid | Spines / border | Ticks |
|---|---|---|---|---|
| `grey` | `#EBEBEB` panel on white canvas | White major and minor grid | None | Muted grey, outward |
| `bw` | White panel and canvas | Light grey; minor thinner | Thin grey border on all sides | Muted grey, outward |
| `linedraw` | White panel and canvas | Black; major very thin, minor thinner | Black border on all sides | Thin black, outward |
| `light` | White panel and canvas | Light grey; thinner than `bw` | Light grey border on all sides | Match border colour |
| `dark` | Approximately 50% grey panel on white canvas | Darker grey, fine lines | None | Dark grey, outward |
| `minimal` | White/blank panel and canvas | Light grey | None | Hidden |
| `classic` | White panel and canvas | Hidden | Left and bottom only | Black, outward |
| `void` | Transparent panel and preferably transparent canvas | Hidden | None | Ticks and tick labels hidden |
| `test` | White panel and canvas | Hidden | Thin grey border on all sides | Muted grey, outward |

Use the colour-mixing formulas and relative line widths in the tagged ggplot2 source as
the source of truth, then choose the nearest stable matplotlib values. Store resolved
hex colours and point widths in the stylesheets so output does not vary across machines.

## Fidelity boundaries

### Supported by stylesheets

The following map directly to matplotlib `rcParams` and belong in `.mplstyle` files:

- figure and axes face colours;
- grid visibility, colour, style, width, and z-order;
- individual spine visibility, colour, and width;
- tick visibility, direction, colour, size, label colour, and padding;
- title and label sizes, colours, placement, and padding;
- legend frame and type settings;
- line and marker defaults; and
- save defaults.

### Not directly equivalent

- ggplot2 facet strips have no core matplotlib equivalent. Preserve sensible subplot
  defaults now and defer strip backgrounds/text until ggstyle has a facet abstraction.
- ggplot2's theme inheritance and `element_blank()` do not map one-to-one to static
  `rcParams`.
- `theme_void()` keeps plot titles and legends while removing axis titles. A stylesheet
  can hide tick labels and make axis-label text transparent, but it may still reserve
  layout space. Test this on every supported matplotlib version. If the result is not
  acceptable, add an explicit axes-level helper in a later change rather than silently
  mutating existing axes from `use_theme()`.
- ggplot2 4.0's `ink`, `paper`, and `accent` parameters can also influence geom defaults.
  The first ggstyle port keeps its existing data colour cycle instead of claiming those
  parameters are implemented.
- Fonts, text measurement, antialiasing, and figure layout will not be pixel-identical to
  R graphics devices.

These differences must appear in the user guide. The documentation should use
“analogue” or “inspired by” rather than promise exact rendering parity.

## Implementation work

### 1. Establish a reference specification

- Record the upstream tag (`v4.0.3`) and source URL in stylesheet comments and tests.
- Convert upstream colour mixes to fixed hex values and record the calculation in this
  plan or a small developer reference table.
- Render one upstream reference plot per theme with the same plot ingredients used by
  the Python gallery: title, axis titles, major/minor grid opportunities, multiple data
  colours, legend, and panels/facets where applicable.
- Decide visual tolerances based on semantics and geometry, not cross-language pixel
  equality.

### 2. Add the stylesheets

Create these self-contained package files:

```text
src/ggstyle/themes/ggstyle-bw.mplstyle
src/ggstyle/themes/ggstyle-linedraw.mplstyle
src/ggstyle/themes/ggstyle-light.mplstyle
src/ggstyle/themes/ggstyle-dark.mplstyle
src/ggstyle/themes/ggstyle-classic.mplstyle
src/ggstyle/themes/ggstyle-void.mplstyle
src/ggstyle/themes/ggstyle-test.mplstyle
```

Audit `ggstyle-minimal.mplstyle` and `ggstyle-grey.mplstyle` at the same time. In
particular, verify whether `grey` should restore visible ggplot2-style tick marks or keep
the current ggstyle simplification. Treat any change to those two themes as a documented
visual change, not incidental cleanup.

Every file should explicitly set the full shared type scale, data colour cycle, layout,
and save settings. Duplication is intentional because `stylesheet()` promises one
standalone file. Add invariant tests to prevent the common settings from drifting.

### 3. Register names and aliases

Update `src/ggstyle/theme.py`:

- add all canonical names to `_THEMES` in the order above;
- add all `theme_*` aliases to `_ALIASES`;
- retain `theme_gray` and `gray` as aliases of `grey` rather than duplicate stylesheets;
- update module and public-function docstrings; and
- preserve the existing unknown-theme error and context-manager behavior.

No import-time `rcParams` mutation is permitted.

### 4. Expand automated tests

Move the theme-specific cases out of `tests/test_frames_themes.py` into a focused
`tests/test_themes.py`, leaving frame-adapter tests in the original module. Cover:

- exact canonical name order and the unchanged default;
- every alias resolving to the expected stylesheet;
- every stylesheet being present in both wheel and sdist builds;
- loading every stylesheet without matplotlib warnings;
- process-wide application and exact context restoration for every theme;
- import-time inertness;
- common type-scale, colour-cycle, layout, and save-setting invariants;
- semantic rcParam assertions for panel colour, grid visibility/colour/width, spine
  visibility, tick visibility, and canvas transparency;
- compatibility with `DateAxis` ticks, independent grid cadence, annotations, collapse,
  and expand;
- `void` followed by another theme, ensuring hidden labels/ticks do not leak through
  global state; and
- `dark` data-colour contrast and series distinguishability.

Add Agg-rendered visual baselines for all nine themes in the pinned renderer job already
planned in `DEVELOPMENT_PLAN.md`. Use both a regular date plot and a small multi-axes plot
so borders and shared edges are visible. Keep numeric rcParam assertions alongside image
baselines; snapshots alone are not sufficient.

### 5. Update examples and documentation

- Change `examples/themes.py` into a deterministic gallery generator for all canonical
  themes and ensure generated filenames use canonical names.
- Add a compact theme gallery to the user guide with each theme's purpose and a note that
  `test` is for stable visual tests.
- Update the README's “Two ship” language, usage examples, and aliases.
- Update API docstrings and generated API pages for `available_themes()`, `stylesheet()`,
  `use_theme()`, and `theme`.
- Add a changelog entry that calls out the new names and any deliberate changes to
  `minimal` or `grey`.
- Link back to the upstream reference version so later ggplot2 changes can be audited.

### 6. Package and compatibility verification

Run the normal quality gates plus clean-artifact checks:

```bash
python -m pytest -q
ruff check .
mypy src
python -m sphinx -W --keep-going -b html docs/source docs/build/html
python -m build
python -m twine check dist/*
```

Install the built wheel into a clean environment and load all paths returned by
`available_themes()`. Run the rendering tests against the lowest supported matplotlib
version and the pinned visual-regression version.

## Delivery sequence

### PR 1: theme registry and presentation themes

- Add `bw`, `linedraw`, `light`, `dark`, and `classic`.
- Add aliases and semantic rcParam tests.
- Audit `minimal` and `grey`.

### PR 2: edge-case themes and visual baselines

- Add `void` and `test`.
- Resolve and document the `void` axis-title/layout limitation.
- Add the nine-theme visual regression gallery.

### PR 3: documentation and release polish

- Publish the gallery and theme comparison table.
- Finish README, API, changelog, and package-artifact verification.
- Release in the next minor version because this adds public names and visible rendering
  behavior; do not fold it into a patch release.

## Acceptance criteria

The integration is complete when:

1. `available_themes()` returns all nine canonical names in the documented order.
2. All ggplot2 `theme_*` spellings above resolve, including both grey/gray spellings.
3. Each theme is available as a standalone, packaged `.mplstyle` file.
4. The theme selected before figure creation produces the documented panel, grid, spine,
   tick, text, legend, and canvas semantics.
5. `minimal` remains the default and importing `ggstyle` remains inert.
6. Switching themes does not alter date-axis placement, collapse mappings, annotations,
   or explicit grid cadence.
7. Context-managed themes restore all prior `rcParams`, including after exceptions.
8. The wheel, sdist, documentation build, static checks, unit tests, and pinned visual
   regression suite all pass from clean environments.
9. Known matplotlib fidelity limits are visible in user-facing documentation.

## Follow-up work not included here

- Runtime theme parameters equivalent to ggplot2's `base_size`, `base_family`,
  `header_family`, `ink`, `paper`, and `accent`.
- Facet-strip styling and other grammar-level layout elements.
- Third-party theme libraries.
- A generic user-authored theme registration API.
- Changes to ggstyle's palette API or default data colours beyond contrast fixes required
  for `dark`.
