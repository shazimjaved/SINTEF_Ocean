"""Score only saved V7 predictions; never fit or choose a model."""
from __future__ import annotations

from common import *
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def methods(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame if c.startswith(("fixed_", "calibrated_", "updated_", "delayed_"))]


def scored(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    base = frame.operational_eligible & frame.observed_truth
    if scope != "broader_forward":
        base &= frame[scope]
    return frame.loc[base]


def summarize(frame: pd.DataFrame, common: dict, daily_rows: list[dict] | None = None) -> list[dict]:
    records = []
    for method in methods(frame):
        # No method-specific finite-value filtering is permitted on scored rows.
        # September has no updated methods, instead of a fictitious update.
        for scope in ["broader_forward", "positive", "recorded_zero", "negative_or_mixed"]:
            part = scored(frame, scope)
            if not len(part):
                continue
            assert np.isfinite(part[method]).all(), (common, method, scope)
            records.append({**common, "method": method, "scope": scope,
                            **metric(part.actual_kw, part[method])})
            if daily_rows is not None:
                for day, p in part.groupby("date", sort=True):
                    daily_rows.append({**common, "date": str(day), "method": method,
                                       "scope": scope, **metric(p.actual_kw, p[method]),
                                       "zero_n": int(p.recorded_zero.sum())})
    return records


def main() -> None:
    prepare()
    dest = OUT / "tables"
    figdir = OUT / "figures"
    dest.mkdir(exist_ok=True)
    figdir.mkdir(exist_ok=True)
    b_rows = []
    daily = []
    bcoverage = []
    for month, name in [(9, "september"), (10, "october")]:
        frame = pd.read_csv(OUT / f"adaptation/predictions_{name}.csv.gz", low_memory=False)
        frame["date"] = day_of(frame).dt.strftime("%Y-%m-%d")
        b_rows.extend(summarize(frame, {"experiment": "B", "period": name}, daily))
        e = frame.operational_eligible
        s = e & frame.observed_truth
        bcoverage.append({"period": name, "calendar_minutes": len(frame), "eligible_n": int(e.sum()),
                          "scored_forward_n": int(s.sum()), "unscored_missing_eligible_n": int((e & ~frame.observed_truth).sum()),
                          "positive_n": int((s & frame.positive).sum()),
                          "zero_n": int((s & frame.recorded_zero).sum()),
                          "negative_or_mixed_n": int((s & frame.negative_or_mixed).sum()),
                          "history_used_on_scored_n": int(frame.loc[s, "history_used"].sum())})
    b = pd.DataFrame(b_rows)
    csv_write(b, dest / "b_adaptation_metrics.csv")
    csv_write(pd.DataFrame(bcoverage), dest / "b_coverage.csv")

    block_rows = []
    cframes = []
    for path in sorted((OUT / "reconstruction").glob("predictions_m*.csv.gz")):
        frame = pd.read_csv(path)
        frame["date"] = day_of(frame).dt.strftime("%Y-%m-%d")
        cframes.append(frame)
        block_rows.extend(summarize(frame, {"experiment": "C", "block_id": frame.block_id.iloc[0],
                                            "period": int(frame.source_month.iloc[0]),
                                            "duration_hours": int(frame.duration_hours.iloc[0])}))
    c = pd.concat(cframes, ignore_index=True)
    assert c.window_end_utc.is_unique, "Artificial gaps must never overlap"
    pooled = []
    for hours, part in c.groupby("duration_hours"):
        pooled.extend(summarize(part, {"experiment": "C", "duration_hours": int(hours),
                                      "period": "all_development_months"}, daily))
    csv_write(pd.DataFrame(block_rows), dest / "c_per_block_metrics.csv")
    cm = pd.DataFrame(pooled)
    csv_write(cm, dest / "c_pooled_duration_metrics.csv")
    perblock = pd.DataFrame(block_rows)
    equalblock = perblock.groupby(["duration_hours", "method", "scope"]).agg(
        scored_blocks=("block_id", "nunique"), total_n=("n", "sum"),
        mean_block_mae_kw=("mae_kw", "mean"), median_block_mae_kw=("mae_kw", "median"),
        worst_block_mae_kw=("mae_kw", "max")).reset_index()
    csv_write(equalblock, dest / "c_equal_block_stability.csv")
    d = pd.DataFrame(daily)
    csv_write(d, dest / "daily_metrics.csv")
    # C daily contributions are by gap duration; all hidden windows are disjoint.
    stability = d[d.n.ge(30)].groupby(["experiment", "period", "method", "scope",
                                      "duration_hours"], dropna=False).agg(
        days_ge30=("date", "nunique"), median_daily_mae_kw=("mae_kw", "median"),
        p90_daily_mae_kw=("mae_kw", lambda x: x.quantile(.9)), worst_daily_mae_kw=("mae_kw", "max"),
        median_daily_bias_kw=("bias_actual_minus_pred_kw", "median")).reset_index()
    csv_write(stability, dest / "daily_stability.csv")

    labels = {"fixed_mean": "Training mean", "fixed_speed_cubic": "Speed³",
              "fixed__B_ridge_full": "Fixed Ridge", "updated__B_ridge_full": "Updated Ridge",
              "calibrated__B_ridge_full": "Delayed residual Ridge",
              "calibrated_positive_history__B_ridge_full": "Positive-history residual",
              "delayed_persistence": "Delayed persistence", "delayed_history_mean": "Delayed history mean"}
    order = list(labels)
    fig, axs = plt.subplots(2, 2, figsize=(13, 8.5))
    for i, month in enumerate(["september", "october"]):
        for j, scope in enumerate(["broader_forward", "positive"]):
            ax = axs[i, j]
            x = b[(b.period == month) & (b.scope == scope)].set_index("method")
            names = [method for method in order if method in x.index]
            ax.bar(np.arange(len(names)), x.loc[names, "mae_kw"], color=[
                "#1f77b4" if name.startswith("fixed_") else "#d62728" for name in names])
            ax.set_xticks(np.arange(len(names)), [labels[name] for name in names], rotation=28, ha="right", fontsize=8)
            ax.set(ylabel="MAE (kW)", title=f"{month.capitalize()} · {scope.replace('_', ' ')} · n={int(x.n.iloc[0]):,}")
            ax.grid(axis="y", alpha=.2)
    fig.suptitle("V7 B: fixed and CONDITIONAL delayed-label scenarios (24h lag, daily refresh)")
    fig.tight_layout()
    fig.savefig(figdir / "b_scenario_mae.png", dpi=170)
    plt.close(fig)

    selected = ["fixed__B_ridge_full", "calibrated__B_ridge_full", "fixed__B_hgb_broad_full",
                "calibrated__B_hgb_broad_full", "delayed_persistence", "delayed_history_mean"]
    ccoverage = pd.read_csv(OUT / "reconstruction/block_coverage.csv").groupby("duration_hours").sum(numeric_only=True)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, scope in zip(axs, ["broader_forward", "positive"]):
        for method in selected:
            x = cm[(cm.method == method) & (cm.scope == scope)].sort_values("duration_hours")
            ax.plot(x.duration_hours, x.mae_kw, marker="o", ms=4, label=method.replace("__", " ").replace("_", " "))
        ax.set(xlabel="Artificial gap duration (hours)", ylabel="Pooled MAE (kW)",
               title=scope.replace("_", " "), xticks=[1, 6, 24])
        ax.set_xticklabels([f"{h}h\nn={int(ccoverage.loc[h, 'scored_forward_n' if scope=='broader_forward' else 'positive_forward_n']):,}"
                            for h in [1,6,24]], fontsize=8)
        ax.grid(alpha=.2)
    axs[0].legend(fontsize=7)
    fig.suptitle("V7 C: different calendar blocks per duration; 24h history lag, daily refresh")
    fig.tight_layout()
    fig.savefig(figdir / "c_gap_duration_mae.png", dpi=170)
    plt.close(fig)

    fig, axs = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True)
    x = perblock[(perblock.duration_hours == 24) & (perblock.scope == "broader_forward")]
    names = list(pd.read_csv(OUT / "reconstruction_blocks.csv").query("duration_hours==24").block_id)
    for method in ["fixed__B_ridge_full", "calibrated__B_ridge_full", "delayed_persistence"]:
        p = x[x.method.eq(method)].set_index("block_id").reindex(names)
        axs[0].plot(np.arange(len(names)), p.mae_kw, marker="o", ms=3, label=method.replace("__", " "))
    cover = pd.read_csv(OUT / "reconstruction/block_coverage.csv").set_index("block_id").reindex(names)
    dates = pd.read_csv(OUT / "reconstruction_blocks.csv").set_index("block_id").reindex(names)
    axs[1].bar(np.arange(len(names)), cover.recorded_zero_forward_n / cover.scored_forward_n.replace(0, np.nan), color=".5")
    axs[1].set(ylim=(0, 1.05), ylabel="Recorded-zero fraction", xticks=np.arange(len(names)),
               xticklabels=[f"{pd.Timestamp(day):%m-%d}\nn={int(n)}" for day,n in zip(dates.start_utc,cover.scored_forward_n)])
    axs[1].tick_params(axis="x", rotation=45)
    axs[0].set_ylabel("24h block MAE (kW)")
    axs[0].legend(fontsize=8)
    axs[0].grid(alpha=.2)
    fig.suptitle("All 24h calendar blocks retained; blank error points have no observed forward truth")
    fig.tight_layout()
    fig.savefig(figdir / "c_24h_block_stability.png", dpi=170)
    plt.close(fig)
    print("PASS: V7 metrics, daily/block stability and three diagnostic figures saved")


if __name__ == "__main__":
    main()
