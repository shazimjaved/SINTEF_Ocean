"""Diagnostic figures from saved V6 results; no fitting or selection."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "task3_v6"
FIG = OUT / "figures"
ARM_COLORS = {"jan_jun": "#1f77b4", "jan_jun_aug": "#d62728"}
LABELS = {"training_mean": "Mean", "speed_cubic": "Speed³",
          "A_hgb_full_v1like": "Restricted HGB", "B_hgb_full": "Engine HGB",
          "B_ridge_full": "Engine Ridge", "B_hgb_broad_full": "Broad-trained HGB"}
ORDER = list(LABELS)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    metrics = pd.read_csv(OUT / "development_metrics.csv")
    daily = pd.read_csv(OUT / "daily_metrics.csv")
    coverage = pd.read_csv(OUT / "evaluation_coverage.csv").set_index("evaluation_month")
    assert set(metrics.evaluation_month) == {"september", "october"}

    # Direct comparisons use exactly the same evaluation timestamps and scope.
    main = metrics[metrics.scope.isin(["positive", "broader_forward"])].copy()
    keys = ["training_arm", "evaluation_month", "scope"]
    baseline_cols = ["mae_kw", "rmse_kw", "r2_score"]
    baseline_mean = main[main.candidate.eq("training_mean")][keys + baseline_cols].rename(
        columns={c: f"training_mean_{c}" for c in baseline_cols})
    baseline_cube = main[main.candidate.eq("speed_cubic")][keys + baseline_cols].rename(
        columns={c: f"speed_cubic_{c}" for c in baseline_cols})
    relative = main[~main.candidate.isin(["training_mean", "speed_cubic"])].merge(
        baseline_mean, on=keys, validate="many_to_one").merge(
        baseline_cube, on=keys, validate="many_to_one")
    for baseline in ["training_mean", "speed_cubic"]:
        relative[f"mae_minus_{baseline}_kw"] = relative.mae_kw - relative[f"{baseline}_mae_kw"]
    relative[["training_arm", "candidate", "evaluation_month", "scope", "n", "mae_kw",
              "rmse_kw", "pearson_r", "r2_score", "bias_actual_minus_pred_kw",
              "training_mean_mae_kw", "speed_cubic_mae_kw",
              "mae_minus_training_mean_kw", "mae_minus_speed_cubic_kw"]].to_csv(
                  OUT / "baseline_relative_comparison.csv", index=False)

    d = daily[daily.n.ge(30)].pivot(index=["candidate", "evaluation_month", "scope", "date"],
                                    columns="training_arm", values=["mae_kw", "n"])
    d.columns = [f"{metric}_{arm}" for metric, arm in d.columns]
    d = d.dropna(subset=["mae_kw_jan_jun", "mae_kw_jan_jun_aug"]).reset_index()
    d["delta_mae_aug_minus_janjun_kw"] = d.mae_kw_jan_jun_aug - d.mae_kw_jan_jun
    day_change = d.groupby(["candidate", "evaluation_month", "scope"]).agg(
        days_ge30=("date", "size"),
        improved_days=("delta_mae_aug_minus_janjun_kw", lambda x: int((x < 0).sum())),
        median_daily_mae_delta_kw=("delta_mae_aug_minus_janjun_kw", "median"),
        p90_daily_mae_delta_kw=("delta_mae_aug_minus_janjun_kw", lambda x: x.quantile(.9)),
        worst_daily_mae_delta_kw=("delta_mae_aug_minus_janjun_kw", "max")
    ).reset_index()
    day_change.to_csv(OUT / "daily_paired_improvement.csv", index=False)

    fig, axs = plt.subplots(2, 2, figsize=(13, 8.5), sharex=True)
    for i, month in enumerate(["september", "october"]):
        for j, scope in enumerate(["positive", "broader_forward"]):
            ax = axs[i, j]
            x = metrics[(metrics.evaluation_month == month) & (metrics.scope == scope)]
            for arm, offset in [("jan_jun", -.13), ("jan_jun_aug", .13)]:
                part = x[x.training_arm.eq(arm)].set_index("candidate").loc[ORDER]
                ax.scatter(np.arange(len(ORDER)) + offset, part.mae_kw,
                           s=65, color=ARM_COLORS[arm], zorder=3,
                           label="Jan–Jun" if arm == "jan_jun" else "Jan–Jun + Aug")
            for k, candidate in enumerate(ORDER):
                yy = x[x.candidate.eq(candidate)].set_index("training_arm").loc[
                    ["jan_jun", "jan_jun_aug"], "mae_kw"].to_numpy()
                ax.plot([k - .13, k + .13], yy, color=".65", lw=1, zorder=1)
            n = int(coverage.loc[month, "positive_n" if scope == "positive" else "forward_with_target"])
            zeros = int(coverage.loc[month, "recorded_zero_n"])
            ax.set_title(f"{month.capitalize()} · {scope.replace('_',' ')} · n={n:,}"
                         + (f"; zeros={zeros:,}" if scope == "broader_forward" else ""), fontsize=10)
            ax.set_ylabel("MAE (kW)")
            ax.grid(axis="y", alpha=.2)
            ax.set_xticks(np.arange(len(ORDER)), [LABELS[c] for c in ORDER], rotation=25, ha="right")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=2, bbox_to_anchor=(.5, 1.01))
    fig.suptitle("Fixed V2 onboard models: effect of adding historical August", y=1.05)
    fig.tight_layout()
    fig.savefig(FIG / "v6_mae_training_history.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, axs = plt.subplots(2, 2, figsize=(12.5, 7.5), sharex="row")
    for i, month in enumerate(["september", "october"]):
        for j, scope in enumerate(["positive", "broader_forward"]):
            ax = axs[i, j]
            x = daily[(daily.candidate == "B_ridge_full") &
                      (daily.evaluation_month == month) & (daily.scope == scope)]
            for arm in ARM_COLORS:
                part = x[(x.training_arm == arm) & x.n.ge(30)].sort_values("date")
                ax.plot(pd.to_datetime(part.date), part.mae_kw, marker="o", markersize=3,
                        lw=1.3, color=ARM_COLORS[arm],
                        label=f"{'Jan–Jun' if arm == 'jan_jun' else 'Jan–Jun + Aug'}"
                              f" ({len(part)} days)")
            ax.set_title(f"{month.capitalize()} · {scope.replace('_', ' ')}")
            ax.set_ylabel("Daily MAE (kW)")
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
            ax.tick_params(axis="x", rotation=25)
    fig.suptitle("Engine Ridge daily error; plotted days have ≥30 labelled minutes")
    fig.tight_layout()
    fig.savefig(FIG / "v6_daily_ridge_stability.png", dpi=180)
    plt.close(fig)

    zero = metrics[metrics.scope.eq("recorded_zero")]
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.5), sharex=True)
    for ax, month in zip(axs, ["september", "october"]):
        x = zero[zero.evaluation_month.eq(month)]
        for arm, offset in [("jan_jun", -.13), ("jan_jun_aug", .13)]:
            part = x[x.training_arm.eq(arm)].set_index("candidate").loc[ORDER]
            ax.scatter(np.arange(len(ORDER)) + offset, part.mae_kw,
                       s=65, color=ARM_COLORS[arm], label=arm)
        ax.set_title(f"{month.capitalize()} · recorded zero n={int(coverage.loc[month,'recorded_zero_n']):,}")
        ax.set_ylabel("MAE on zero readings (kW)")
        ax.set_xticks(np.arange(len(ORDER)), [LABELS[c] for c in ORDER], rotation=25, ha="right")
        ax.grid(axis="y", alpha=.2)
    axs[0].legend(["Jan–Jun", "Jan–Jun + Aug"], fontsize=8, loc="lower left")
    fig.suptitle("Predictions during recorded-zero power states (diagnostic only)")
    fig.tight_layout()
    fig.savefig(FIG / "v6_zero_state_error.png", dpi=180)
    plt.close(fig)
    print("PASS: three V6 diagnostic figures rendered from saved CSV results")


if __name__ == "__main__":
    main()
