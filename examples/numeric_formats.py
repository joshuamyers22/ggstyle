"""Apply pure ggstyle numeric labellers to native Matplotlib axes."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ggstyle as gs

x = np.arange(5)
revenue = np.array([0, 1_250_000, 2_000_000, 2_750_000, 3_500_000])
share = np.array([0.05, 0.12, 0.18, 0.24, 0.31])

with gs.theme("minimal"):
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(x, revenue)
    axes[0].yaxis.set_major_formatter(
        gs.as_formatter(gs.label_currency("$", scale=1_000_000, decimals=1, suffix="M"))
    )
    axes[0].set_title("Revenue")

    axes[1].plot(x, share)
    axes[1].yaxis.set_major_formatter(gs.as_formatter(gs.label_percent(decimals=0)))
    axes[1].set_title("Share")

    figure.tight_layout()
    figure.savefig("numeric-formats.png", dpi=110)
    plt.close(figure)

print("wrote numeric-formats.png")
