"""Visual smoke test for the two themes, driven from a polars frame."""

import datetime as dt

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

import ggstyle as gs

rng = np.random.default_rng(7)

# A polars frame in, no pandas anywhere in the caller's code.
days = pl.date_range(dt.date(2020, 1, 1), dt.date(2021, 12, 31), "1d", eager=True)
frame = pl.DataFrame({"date": days}).filter(pl.col("date").dt.weekday() <= 5)
n = len(frame)
frame = frame.with_columns(
    a=pl.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.011, n)))),
    b=pl.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.008, n)))),
    c=pl.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.014, n)))),
)

x = frame["date"].to_numpy()

for name in gs.available_themes():
    with gs.theme(name):
        fig, ax = plt.subplots(figsize=(9, 5))
        for column in ("a", "b", "c"):
            ax.plot(x, frame[column].to_numpy(), label=column.upper())

        gs.dates(ax, data=frame["date"]).ticks("quarterly").fmt("concise").span(
            "2020-02-19", "2020-03-23", label="drawdown"
        )

        ax.set_title(f"ggstyle theme: {name}", loc="left")
        ax.set_ylabel("index level")
        ax.legend(loc="upper right", ncols=3)
        fig.savefig(f"theme-{name}.png")
        plt.close(fig)
        print(f"wrote theme-{name}.png")

# Default with no argument must be minimal.
gs.use_theme()
assert plt.rcParams["axes.facecolor"] == "white"
print("default theme:", gs.DEFAULT_THEME, "| order:", gs.available_themes())
