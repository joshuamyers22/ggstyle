# Visual regression workflow

The pixel suite protects user-visible rendering that geometry assertions alone cannot
cover. It uses Matplotlib's maintained `compare_images` utility instead of an additional
snapshot plugin. Every figure builder also contains numeric geometry assertions, so an
accepted image cannot conceal a coordinate error.

## Canonical environment

Pixel comparisons run only in the dedicated `visual` CI job and when
`GGSTYLE_RUN_VISUAL=1` is set locally. The canonical renderer is:

- Ubuntu 24.04 and CPython 3.12;
- Matplotlib 3.11.1 using Agg and its bundled FreeType 2.14.3;
- NumPy 2.5.2, pandas 3.0.5, Pillow 12.3.0, and pytest 9.1.1;
- the bundled DejaVu Sans font, 100 DPI, `LC_ALL=C`, and `TZ=UTC`; and
- an RMS pixel tolerance of 0.1 on the 0–255 color scale.

Those direct versions are pinned in the `visual` dependency group; `uv.lock` pins the
remaining renderer dependency graph. The first visual test checks the versions, backend,
font, locale, timezone, and FreeType version before any baseline comparison. Pixel tests
must not be enabled in the general Python or operating-system matrix.

## Running comparisons

Install and run the exact visual group with:

```bash
uv sync --frozen --group visual
make visual
```

The suite writes current renders to `build/visual-results`. A mismatch also produces an
amplified `*.actual-failed-diff.png` beside the actual image and reports the RMS value and
all three paths. CI uploads that directory for 14 days when the job fails. These outputs
are diagnostic artifacts and are not committed.

## Updating baselines

Only update a baseline for an intentional, reviewed rendering change. From the pinned
environment, run:

```bash
make visual-update
make visual
```

`visual-update` passes an explicit overwrite flag to the generator; the underlying script
refuses to replace files without it or outside the exact pinned renderer. Inspect every
changed PNG and, for an existing baseline, inspect the old/new image diff before
committing. The pull-request description must explain why each changed pixel surface is
expected. Reviewers should reject broad or unexplained snapshot churn even when the
comparisons pass afterward.

Canonical baselines live in `tests/baseline_images`. The initial set covers expanded and
collapsed irregular lines, date annotations and spans, synchronized panels with distinct
observations, and a gallery of all nine themes. Future collection support adds its own
geometry assertion and focused baseline rather than enlarging an unrelated image.
