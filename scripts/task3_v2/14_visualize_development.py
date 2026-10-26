"""Plot saved V2 development results; does not fit models or read December."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("outputs/task3_v2/experiments")
FOUR = ["A_hgb_full_v1like", "A_hgb_recent90", "B_hgb_full", "B_ridge_recent90"]
LABELS = {
    "A_hgb_full_v1like": "Restricted HGB, full history",
    "A_hgb_recent90": "Restricted HGB, recent 90 days",
    "B_hgb_full": "Engine HGB, full history",
    "B_ridge_recent90": "Engine Ridge, recent 90 days",
}


def main():
    result = pd.read_csv(ROOT / "v2_walkforward_results.csv")
    result = result[(result.scope == "headline") & result.candidate.isin(FOUR)]
    assert len(result) == 16 and set(result.fold) == {"apr", "may", "jun", "aug"}
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    for name in FOUR:
        data = result[result.candidate == name].set_index("fold").loc[["apr", "may", "jun", "aug"]]
        axes[0].plot(range(4), data.mae_kw, marker="o", linewidth=2, label=LABELS[name])
        axes[1].plot(range(4), data.r2_score, marker="o", linewidth=2)
        for x, n in enumerate(data.n):
            if name == FOUR[0]:
                axes[0].annotate(f"n={n:,}", (x, 0), xycoords=("data", "axes fraction"),
                                 xytext=(0, 6), textcoords="offset points", ha="center", fontsize=8)
    axes[0].set_ylabel("Headline MAE (kW)")
    axes[1].set_ylabel("R² (sklearn)")
    axes[1].axhline(0, color="0.4", linewidth=1)
    axes[1].set_xticks(range(4), ["Apr", "May", "Jun", "Aug"])
    axes[1].set_xlabel("Chronological development fold (training uses earlier allowed months)")
    axes[0].legend(loc="upper left", fontsize=8, ncol=2)
    axes[0].set_title("Development-fold error and fit quality; no December model selection")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(ROOT / "v2_development_fold_comparison.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
