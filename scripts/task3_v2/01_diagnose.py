"""Internal V2 root-cause diagnostics from original raw and V1 minute tables.

Read-only for raw/V1. No model selection, fitting or December-based tuning.
Writes bounded diagnostic CSVs and plots under outputs/task3_v2/phase1.
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_config import COLUMN_TO_QID, TARGET

OUT = Path("outputs/task3_v2/phase1")
DATA = Path("outputs/task3/data")
RAW = Path("data/raw")
FEATURES = ["STW_kn", "SOG_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct",
            "ME_ScavAirPressure_bar", "ME_TC_RPM_Transducer", "WIND_RelSpeed_kn"]
READ = ["window_end_utc", TARGET, "target_n", "target_min", "target_negative_n"] + FEATURES
ROLES = {**{m: "train" for m in range(1, 7)}, 7: "quarantine", 8: "validation",
         9: "stress", 10: "stress", 11: "quarantine", 12: "diagnostic_holdout"}


def headline(d):
    return (d.target_n.gt(0) & d.STW_kn.ge(3) & d[TARGET].gt(0)
            & d.target_min.ge(0) & d.target_negative_n.eq(0))


def broad(d):
    return d.target_n.gt(0) & d.STW_kn.ge(3)


def load_month(m):
    d = pd.read_csv(DATA / f"minute_2024_{m:02d}.csv.gz", usecols=READ,
                    dtype={c: "float32" for c in READ if c not in {"window_end_utc", "target_n", "target_negative_n"}})
    d["month"] = m
    d["role"] = ROLES[m]
    return d


def describe(d, m):
    b = d.loc[broad(d)]
    h = d.loc[headline(d)]
    row = {"month": m, "role": ROLES[m], "calendar_minutes": len(d),
           "target_minutes": int(d.target_n.gt(0).sum()),
           "forward_target_minutes": len(b), "headline_minutes": len(h),
           "forward_zero_target": int(b[TARGET].eq(0).sum()),
           "forward_negative_target": int(b[TARGET].lt(0).sum()),
           "forward_any_negative_raw": int(b.target_negative_n.gt(0).sum())}
    for name, frame in [("headline", h), ("broad", b)]:
        for col in [TARGET] + FEATURES:
            s = frame[col].dropna()
            row[f"{name}_{col}_n"] = len(s)
            row[f"{name}_{col}_mean"] = float(s.mean()) if len(s) else np.nan
            row[f"{name}_{col}_std"] = float(s.std()) if len(s) else np.nan
            row[f"{name}_{col}_median"] = float(s.median()) if len(s) else np.nan
            row[f"{name}_{col}_p10"] = float(s.quantile(.1)) if len(s) else np.nan
            row[f"{name}_{col}_p90"] = float(s.quantile(.9)) if len(s) else np.nan
    return row


def relationships(d, m):
    h = d.loc[headline(d)]
    rows = []
    for col in FEATURES:
        paired = h[[TARGET, col]].dropna()
        x = paired[col].to_numpy(dtype=np.float64)
        y = paired[TARGET].to_numpy(dtype=np.float64)
        if len(paired) < 10 or np.std(x) == 0 or np.std(y) == 0:
            continue
        slope = np.cov(x, y, ddof=0)[0, 1] / np.var(x)
        rows.append({"month": m, "role": ROLES[m], "feature": col, "n": len(paired),
                     "pearson_r": float(np.corrcoef(x, y)[0, 1]),
                     "slope_kw_per_unit": float(slope),
                     "intercept_kw": float(y.mean() - slope*x.mean()),
                     "target_mean_kw": float(y.mean()), "feature_mean": float(x.mean())})
    return rows


def daily(d, m):
    h = d.loc[headline(d)].copy()
    h["date"] = h.window_end_utc.str[:10]
    agg = h.groupby("date").agg(
        n=(TARGET, "size"), power_mean_kw=(TARGET, "mean"),
        power_median_kw=(TARGET, "median"), stw_mean_kn=("STW_kn", "mean"),
        rpm_mean=("ME_RPM_CAMS", "mean"), fuel_load_mean_pct=("ME_FuelLoad_pct", "mean"),
        pressure_mean_bar=("ME_ScavAirPressure_bar", "mean")).reset_index()
    agg["month"] = m
    return agg


def bins_from_train(train, cols):
    edges = {}
    for col in cols:
        s = train[col].dropna()
        q = np.unique(s.quantile([0, .2, .4, .6, .8, 1]).to_numpy(dtype=np.float64))
        q[0], q[-1] = -np.inf, np.inf
        if len(q) < 3:
            raise ValueError(f"Not enough training quantile edges for {col}")
        edges[col] = q
    return edges


def conditional_cells(frame, period, edges, cols):
    base = ["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
    h = frame.loc[headline(frame), [TARGET]+base].dropna(subset=[TARGET]+cols).copy()
    for col in cols:
        h[f"bin_{col}"] = pd.cut(h[col], edges[col], labels=False, include_lowest=True)
    keys = [f"bin_{c}" for c in cols]
    grouped = h.groupby(keys, observed=True).agg(n=(TARGET, "size"),
        power_mean_kw=(TARGET, "mean"), power_std_kw=(TARGET, "std"),
        stw_mean_kn=("STW_kn", "mean"), rpm_mean=("ME_RPM_CAMS", "mean"),
        fuel_mean_pct=("ME_FuelLoad_pct", "mean"),
        pressure_mean_bar=("ME_ScavAirPressure_bar", "mean")).reset_index()
    grouped["period"] = period
    grouped["complete_case_n"] = len(h)
    return grouped


def compare_cells(cells, cols, reference="jan_jun_train"):
    keys = [f"bin_{c}" for c in cols]
    train = cells[cells.period == reference]
    rows = []
    detail = []
    for period in ["august", "sep_oct", "december"]:
        other = cells[cells.period == period]
        merged = train.merge(other, on=keys, suffixes=("_train", "_other"))
        merged = merged[(merged.n_train >= 30) & (merged.n_other >= 30)].copy()
        merged["period"] = period
        merged["target_shift_kw"] = merged.power_mean_kw_other - merged.power_mean_kw_train
        merged["weight"] = np.minimum(merged.n_train, merged.n_other)
        detail.append(merged)
        if len(merged):
            shift = np.average(merged.target_shift_kw, weights=merged.weight)
            rows.append({"period": period, "dimensions": "+".join(cols),
                         "common_cells_n": len(merged), "matched_min_weight": int(merged.weight.sum()),
                         "other_minutes_in_common_cells": int(merged.n_other.sum()),
                         "target_shift_kw_weighted": float(shift),
                         "cell_shift_median_kw": float(merged.target_shift_kw.median()),
                         "cell_shift_p10_kw": float(merged.target_shift_kw.quantile(.1)),
                         "cell_shift_p90_kw": float(merged.target_shift_kw.quantile(.9))})
        else:
            rows.append({"period": period, "dimensions": "+".join(cols),
                         "common_cells_n": 0, "matched_min_weight": 0,
                         "other_minutes_in_common_cells": 0,
                         "target_shift_kw_weighted": np.nan,
                         "cell_shift_median_kw": np.nan,
                         "cell_shift_p10_kw": np.nan, "cell_shift_p90_kw": np.nan})
    return rows, pd.concat(detail, ignore_index=True) if detail else pd.DataFrame()


def trace_raw(months):
    columns = [TARGET, "STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
    qid_to_col = {COLUMN_TO_QID[c]: c for c in columns}
    dictionary = pd.read_csv("outputs/tables/data_dictionary.csv", keep_default_na=False).set_index("qid")
    target_qid = COLUMN_TO_QID[TARGET]
    if dictionary.loc[target_qid, "quantity_name"] != "Vessel Propeller Shaft Mechanical Power" or dictionary.loc[target_qid, "unit"].lower() != "kw":
        raise ValueError("Target QID/name/unit mismatch with registered dictionary")
    traces, checks = [], []
    for month in months:
        minute = load_month(month)
        eligible = minute[headline(minute)].dropna(subset=["ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"])
        selected = eligible.iloc[len(eligible)//2]
        end = pd.Timestamp(selected.window_end_utc)
        start_prefix = (end - pd.Timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
        values = {col: [] for col in columns}
        timestamps = {col: [] for col in columns}
        with (RAW / f"{month}.csv").open(newline="", encoding="utf-8-sig") as file:
            for row in csv.reader(file):
                if len(row) >= 3 and row[1] in qid_to_col and row[0][:16] == start_prefix:
                    col = qid_to_col[row[1]]
                    values[col].append(float(row[2]))
                    timestamps[col].append(row[0])
        for col in columns:
            raw = values[col]
            recorded = float(selected[col])
            mean = float(np.mean(raw)) if raw else np.nan
            okay = bool(raw and abs(mean-recorded) <= max(.02, abs(mean)*2e-6))
            if col == TARGET:
                okay &= len(raw) == int(selected.target_n)
                okay &= abs(min(raw)-float(selected.target_min)) <= .02
                okay &= sum(v < 0 for v in raw) == int(selected.target_negative_n)
            traces.append({"month": month, "window_end_utc": selected.window_end_utc,
                           "window_start_prefix": start_prefix, "column": col,
                           "qid": COLUMN_TO_QID[col], "unit": dictionary.loc[COLUMN_TO_QID[col], "unit"],
                           "raw_n": len(raw), "raw_mean": mean,
                           "minute_value": recorded, "raw_min": min(raw) if raw else np.nan,
                           "first_raw_ts": min(timestamps[col]) if raw else "",
                           "last_raw_ts": max(timestamps[col]) if raw else "",
                           "pass": okay})
            checks.append(okay)
    return pd.DataFrame(traces), all(checks)


def plots(monthly, rel, daily_table, cells):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for feat, ax in [("ME_FuelLoad_pct", axes[0]), ("ME_RPM_CAMS", axes[1])]:
        sub = rel[rel.feature == feat]
        ax.errorbar(sub.month, sub.intercept_kw, fmt="o-", label="intercept")
        ax.set(xlabel="2024 month", ylabel="Within-month linear intercept (kW)",
               title=f"Target relation with {feat}")
        ax.axvline(7.5, color="gray", ls=":", lw=1)
    fig.tight_layout()
    fig.savefig(OUT / "monthly_target_relation_intercepts.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axes[0].plot(daily_table.date, daily_table.power_mean_kw, lw=1)
    axes[0].set(ylabel="Headline daily mean power (kW)")
    axes[1].plot(daily_table.date, daily_table.stw_mean_kn, lw=1, label="STW kn")
    axes[1].plot(daily_table.date, daily_table.fuel_load_mean_pct/10, lw=1,
                 label="Fuel load % / 10")
    axes[1].legend()
    axes[1].set(ylabel="Speed / scaled load", xlabel="2024 date")
    axes[1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(OUT / "daily_power_speed_load.png", dpi=180)
    plt.close(fig)
    subset = cells[(cells.period.isin(["jan_jun_train", "august", "sep_oct", "december"]))]
    fig, ax = plt.subplots(figsize=(8, 5))
    for period, d in subset.groupby("period"):
        ax.scatter(d.stw_mean_kn, d.power_mean_kw, s=np.sqrt(d.n)*4, alpha=.5,
                   label=period)
    ax.set(xlabel="Mean STW within train-defined sensor bins (kn)",
           ylabel="Mean shaft power (kW)", title="Power at comparable speed/engine states")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "conditional_power_cells.png", dpi=180)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_months = {}
    summaries, relations, days = [], [], []
    for m in range(1, 13):
        d = load_month(m)
        all_months[m] = d
        summaries.append(describe(d, m))
        relations.extend(relationships(d, m))
        days.append(daily(d, m))
    monthly = pd.DataFrame(summaries)
    rel = pd.DataFrame(relations)
    daily_table = pd.concat(days, ignore_index=True)
    monthly.to_csv(OUT / "monthly_distributions.csv", index=False)
    rel.to_csv(OUT / "monthly_target_relationships.csv", index=False)
    daily_table.to_csv(OUT / "daily_operating_summary.csv", index=False)

    train = pd.concat([all_months[m] for m in range(1, 7)], ignore_index=True)
    periods = {"jan_jun_train": train, "august": all_months[8],
               "sep_oct": pd.concat([all_months[9], all_months[10]], ignore_index=True),
               "december": all_months[12]}
    all_cells, shifts, details = [], [], []
    for cols in [["STW_kn", "ME_RPM_CAMS"],
                 ["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]]:
        edges = bins_from_train(train.loc[headline(train)], cols)
        cells = pd.concat([conditional_cells(frame, period, edges, cols)
                           for period, frame in periods.items()], ignore_index=True)
        cells["dimensions"] = "+".join(cols)
        rows, detail = compare_cells(cells, cols)
        shifts.extend(rows)
        all_cells.append(cells)
        if len(detail):
            detail["dimensions"] = "+".join(cols)
            details.append(detail)
        if len(cols) == 4:
            plot_cells = cells
    all_cells = pd.concat(all_cells, ignore_index=True)
    all_cells.to_csv(OUT / "conditional_cells.csv", index=False)
    pd.DataFrame(shifts).to_csv(OUT / "conditional_shift_summary.csv", index=False)
    pd.concat(details, ignore_index=True).to_csv(OUT / "conditional_common_cells.csv", index=False)
    trace, pass_all = trace_raw([1, 8, 10, 12])
    trace.to_csv(OUT / "raw_minute_trace.csv", index=False)
    plots(monthly, rel, daily_table, plot_cells)
    print({"raw_trace_pass": pass_all, "raw_trace_rows": len(trace),
           "months": len(monthly), "conditional_comparisons": len(shifts)})
    if not pass_all:
        raise SystemExit("Raw-to-minute reconstruction failed")


if __name__ == "__main__":
    main()
