"""Visual smoke test: four panels exercising the v0.1 surface."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import ggstyle as gs

rng = np.random.default_rng(0)

# Two years of weekdays, so weekends are genuine gaps.
days = pd.bdate_range("2020-01-01", "2021-12-31")
price = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, len(days))))

fig, axes = plt.subplots(2, 2, figsize=(14, 8))

# 1. Zero config: adopt a plain matplotlib plot, change nothing.
ax = axes[0, 0]
ax.plot(days, price, lw=1)
gs.dates(ax)
ax.set_title("Zero config (adopted)", loc="left")

# 2. Explicit cadence, format, and a drawdown span.
ax = axes[0, 1]
ax.plot(days, price, lw=1)
gs.dates(ax).ticks("quarterly").fmt("quarter").span(
    "2020-02-19", "2020-03-23", label="drawdown"
).vline("2021-01-27", label="squeeze")
ax.set_title("Quarterly ticks, annotated", loc="left")

# 3. Collapsed weekends, monthly ticks landing on real trading days.
ax = axes[1, 0]
ax.plot(days, price, lw=1)
gs.dates(ax).collapse().ticks("monthly").fmt("concise").zoom("2020-01", "2020-06")
ax.set_title("Collapsed gaps, H1 2020", loc="left")

# 4. Intraday: one session, minute bars.
ax = axes[1, 1]
session = pd.date_range("2024-03-15 09:30", "2024-03-15 16:00", freq="min")
intraday = 100 + np.cumsum(rng.normal(0, 0.02, len(session)))
ax.plot(session, intraday, lw=1)
gs.dates(ax).ticks(every="1h").fmt("time").grid("1h")
ax.set_title("Intraday session", loc="left")

for row in axes:
    for ax in row:
        ax.spines[["top", "right"]].set_visible(False)

fig.tight_layout()
fig.savefig("smoke.png", dpi=110)
print("wrote smoke.png")

# Report what actually landed, so the numbers can be checked against the picture.
for name, ax in zip(
    ["zero-config", "quarterly", "collapsed", "intraday"], axes.ravel(), strict=True
):
    text = [t.get_text().replace("\n", "|") for t in ax.get_xticklabels()]
    print(f"{name:12s} {len(text):2d} ticks: {text[:8]}")
