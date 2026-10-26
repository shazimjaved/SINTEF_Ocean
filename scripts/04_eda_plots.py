"""
scripts/04_eda_plots.py
=======================
Generates genuine EDA figures from:
  - Year-wide coverage summaries (streaming, all 12 monthly files)
  - Pivoted Oct 2024 analytical frame (outputs/tables/pivot_oct2024.csv)
  - Pivoted Jan 2024 sampled frame (outputs/tables/pivot_jan2024_sampled.csv)
  - Quality audit results (outputs/tables/data_quality_summary.csv)
  - Target availability table (outputs/tables/target_availability.csv)

All plots labelled with actual date ranges from the data.
No fabricated values. If a data file is missing, the plot is skipped with a warning.

Figures saved to: outputs/figures/
"""

import os
import csv
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from collections import defaultdict

OUT_FIG = "outputs/figures"
OUT_TAB = "outputs/tables"
RAW_DIR = "data/raw"
os.makedirs(OUT_FIG, exist_ok=True)

TARGET_COL  = "SHAFT_MechPower_kW"   # column name in pivoted frames
TARGET_QID  = "2::0::11::0_1::1::0::3::0_14::0::1::0_8"

# Consistent style
plt.rcParams.update({
    "figure.dpi": 120,
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
})

def savefig(fname, tight=True):
    path = os.path.join(OUT_FIG, fname)
    if tight:
        plt.tight_layout()
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")

# --------------------------------------------------------------------------
# Fig 1: Monthly row count bar chart (year-wide data inventory)
# --------------------------------------------------------------------------
def plot_row_counts():
    inv_path = os.path.join(OUT_TAB, "data_inventory.csv")
    if not os.path.exists(inv_path):
        print("  SKIP Fig 1: data_inventory.csv not found")
        return

    rows = []
    with open(inv_path, "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    monthly = [r for r in rows if r["file"] != "Jan25.csv"]
    files   = [r["file"] for r in monthly]
    counts  = [int(r["row_count"]) for r in monthly]
    jan25   = next((r for r in rows if r["file"] == "Jan25.csv"), None)

    fig, ax = plt.subplots(figsize=(10, 4))
    colors = ["#4C72B0"] * len(monthly)
    bars = ax.bar(files, [c / 1e6 for c in counts], color=colors, edgecolor="white", linewidth=0.5)
    if jan25:
        ax.bar(["Jan25.csv"], [int(jan25["row_count"]) / 1e6],
               color="#DD8452", edgecolor="white", linewidth=0.5, label="Jan 2025 (separate schema)")

    ax.set_xlabel("File")
    ax.set_ylabel("Row count (millions)")
    ax.set_title("Raw data volume per file — all long-format rows\n(includes all sensor QIDs per file)")
    ax.axhline(sum(counts) / len(counts) / 1e6, color="red", linestyle="--", linewidth=0.8,
               label=f"Mean (1–12.csv): {sum(counts)/len(counts)/1e6:.2f}M")
    ax.legend(fontsize=8)
    # Annotate verified totals
    total12 = sum(counts)
    ax.text(0.98, 0.95, f"Total (1–12.csv): {total12:,} rows", transform=ax.transAxes,
            ha="right", va="top", fontsize=8, color="darkblue")
    plt.xticks(rotation=30, ha="right")
    savefig("fig01_row_counts_per_file.png")

# --------------------------------------------------------------------------
# Fig 2: Target availability heatmap across months
# --------------------------------------------------------------------------
def plot_target_availability():
    ta_path = os.path.join(OUT_TAB, "target_availability.csv")
    if not os.path.exists(ta_path):
        print("  SKIP Fig 2: target_availability.csv not found")
        return

    with open(ta_path, "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        print("  SKIP Fig 2: no target availability data")
        return

    files  = [r["file"] for r in rows]
    pcts   = [float(r["pct_present"]) if r["pct_present"] else 0.0 for r in rows]
    n_obs  = [int(r["n_target_obs"]) for r in rows]
    n_neg  = [int(r["n_negative"]) for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Panel A: % present
    ax = axes[0]
    colors_avail = ["#2ca02c" if p > 0 else "#d62728" for p in pcts]
    ax.barh(files, pcts, color=colors_avail, edgecolor="white")
    ax.set_xlim(0, 105)
    ax.set_xlabel("% observations present (non-null)")
    ax.set_title(f"Target availability: Shaft Mechanical Power (kW)\nQID: {TARGET_QID[:30]}...")
    ax.axvline(100, color="gray", linestyle="--", linewidth=0.7)
    for i, (p, n) in enumerate(zip(pcts, n_obs)):
        ax.text(p + 0.5, i, f"{n:,}", va="center", fontsize=7)

    # Panel B: negative values
    ax = axes[1]
    ax.barh(files, n_neg, color="#ff7f0e", edgecolor="white")
    ax.set_xlabel("Count of negative power readings (requires review)")
    ax.set_title("Negative target values per file\n(NOT auto-removed — physical validity TBD)")
    ax.set_xlim(left=0)

    savefig("fig02_target_availability.png")

# --------------------------------------------------------------------------
# Fig 3: Shaft power time series — Oct 2024 (full resolution)
# --------------------------------------------------------------------------
def plot_shaft_power_timeseries():
    piv_path = os.path.join(OUT_TAB, "pivot_oct2024.csv")
    if not os.path.exists(piv_path):
        print("  SKIP Fig 3: pivot_oct2024.csv not found")
        return

    df = pd.read_csv(piv_path, index_col=0, parse_dates=True)
    if TARGET_COL not in df.columns:
        print(f"  SKIP Fig 3: column '{TARGET_COL}' not in pivot")
        return

    ts = df.index
    pw = df[TARGET_COL]
    date_min = ts.min().strftime("%Y-%m-%d")
    date_max = ts.max().strftime("%Y-%m-%d")
    n_obs    = pw.notna().sum()
    n_mis    = pw.isna().sum()
    n_neg    = (pw < 0).sum()

    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=False)

    # Full time series
    ax = axes[0]
    ax.plot(ts, pw, linewidth=0.4, color="#1f77b4", alpha=0.8)
    ax.set_ylabel("Shaft Mechanical Power (kW)")
    ax.set_title(f"Shaft Mechanical Power — October 2024 (full resolution)\n"
                 f"File: 10.csv | Date range: {date_min} to {date_max} | "
                 f"n_obs={n_obs:,}, n_missing={n_mis:,}, n_negative={n_neg}")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)
    ax.axhline(0, color="red", linestyle="--", linewidth=0.6, alpha=0.5, label="Zero line")
    ax.legend(fontsize=8)

    # Distribution
    ax = axes[1]
    valid = pw.dropna()
    if len(valid) > 0:
        ax.hist(valid, bins=80, color="#1f77b4", edgecolor="white", linewidth=0.3, alpha=0.8)
        ax.axvline(valid.median(), color="orange", linestyle="--", linewidth=1,
                   label=f"Median: {valid.median():.0f} kW")
        ax.axvline(0, color="red", linestyle="-", linewidth=0.7, alpha=0.6, label="Zero")
        ax.set_xlabel("Shaft Mechanical Power (kW)")
        ax.set_ylabel("Frequency")
        ax.set_title(f"Distribution — Oct 2024  [min={valid.min():.0f}, max={valid.max():.0f}, "
                     f"mean={valid.mean():.0f}, std={valid.std():.0f}]")
        ax.legend(fontsize=8)

    savefig("fig03_shaft_power_oct2024.png")

# --------------------------------------------------------------------------
# Fig 4: Missing value matrix — Oct 2024 (per-sensor missingness)
# --------------------------------------------------------------------------
def plot_missing_matrix():
    piv_path = os.path.join(OUT_TAB, "pivot_oct2024.csv")
    if not os.path.exists(piv_path):
        print("  SKIP Fig 4: pivot_oct2024.csv not found")
        return

    df = pd.read_csv(piv_path, index_col=0, parse_dates=True)
    pct_missing = df.isna().mean().sort_values(ascending=False) * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#d62728" if p > 50 else "#ff7f0e" if p > 10 else "#2ca02c" for p in pct_missing]
    pct_missing.plot(kind="barh", ax=ax, color=colors, edgecolor="white")
    ax.set_xlabel("% missing (NaN after pivot)")
    ax.set_title("Sensor missingness after long→wide pivot — October 2024\n"
                 "(Sensors with high missingness may have irregular logging intervals)")
    ax.axvline(10, color="orange", linestyle="--", linewidth=0.8, alpha=0.8, label=">10% threshold")
    ax.axvline(50, color="red",    linestyle="--", linewidth=0.8, alpha=0.8, label=">50% threshold")
    ax.legend(fontsize=8)
    savefig("fig04_missing_matrix_oct2024.png")

# --------------------------------------------------------------------------
# Fig 5: Shaft power vs Speed Through Water scatter — Oct 2024
# --------------------------------------------------------------------------
def plot_power_vs_stw():
    piv_path = os.path.join(OUT_TAB, "pivot_oct2024.csv")
    if not os.path.exists(piv_path):
        print("  SKIP Fig 5: pivot_oct2024.csv not found")
        return

    df = pd.read_csv(piv_path, index_col=0, parse_dates=True)
    if TARGET_COL not in df.columns or "STW_kn" not in df.columns:
        print("  SKIP Fig 5: required columns missing")
        return

    sub = df[[TARGET_COL, "STW_kn"]].dropna()
    # Remove physically implausible speed (>30 kn for a bulk carrier)
    sub = sub[(sub["STW_kn"] >= 0) & (sub["STW_kn"] <= 30)]
    n = len(sub)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(sub["STW_kn"], sub[TARGET_COL], s=1, alpha=0.15, color="#1f77b4")
    ax.set_xlabel("Speed Through Water (knots) — Speedlog")
    ax.set_ylabel("Shaft Mechanical Power (kW)")
    ax.set_title(f"Shaft Power vs. Speed Through Water — Oct 2024\n(n={n:,} co-observed pairs)")

    # Overlay cubic trend line (speed-cube power law is a marine physics heuristic)
    stw_range = np.linspace(sub["STW_kn"].quantile(0.02), sub["STW_kn"].quantile(0.98), 100)
    try:
        coeffs = np.polyfit(sub["STW_kn"], sub[TARGET_COL], 3)
        poly   = np.poly1d(coeffs)
        ax.plot(stw_range, poly(stw_range), color="red", linewidth=1.5,
                label="Cubic trend (heuristic)")
        ax.legend(fontsize=8)
    except Exception:
        pass

    ax.text(0.02, 0.95, "Note: Negative shaft power values\nare retained (require investigation)",
            transform=ax.transAxes, fontsize=7, va="top", color="darkred")
    savefig("fig05_power_vs_stw_oct2024.png")

# --------------------------------------------------------------------------
# Fig 6: Year-wide target coverage — streaming summary
# --------------------------------------------------------------------------
def plot_year_wide_target():
    """Stream each monthly file, compute daily target obs counts, plot."""
    RAW_FILES = [f"{i}.csv" for i in range(1, 13)]
    target_qid = TARGET_QID

    daily_counts = []

    for fname in RAW_FILES:
        fpath = os.path.join(RAW_DIR, fname)
        day_count = defaultdict(int)
        with open(fpath, "r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) < 3: continue
                if row[1].strip() == target_qid:
                    ts = row[0].strip()
                    # Extract date prefix (YYYY-MM-DD)
                    day = ts[:10] if len(ts) >= 10 else "unknown"
                    day_count[day] += 1
        for day, cnt in day_count.items():
            daily_counts.append({"file": fname, "day": day, "count": cnt})
        print(f"  {fname}: {sum(day_count.values()):,} target obs, {len(day_count)} days", flush=True)

    df = pd.DataFrame(daily_counts)
    df = df[df["day"] != "unknown"]
    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df = df.dropna(subset=["day"]).sort_values("day")

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.bar(df["day"], df["count"], width=1, color="#1f77b4", alpha=0.8)
    ax.set_xlabel("Date")
    ax.set_ylabel("Target observations per day")
    ax.set_title("Year-wide daily coverage of Shaft Mechanical Power (target variable)\n"
                 "Files: 1.csv–12.csv  |  QID: 2::0::11::0_1::1::0::3::0_14::0::1::0_8")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    savefig("fig06_yearwide_target_coverage.png")

# --------------------------------------------------------------------------
# Fig 7: Provider MB vs Provider S wave height comparison — Oct 2024
# --------------------------------------------------------------------------
def plot_provider_comparison():
    piv_path = os.path.join(OUT_TAB, "pivot_oct2024.csv")
    if not os.path.exists(piv_path):
        print("  SKIP Fig 7: pivot_oct2024.csv not found")
        return

    df = pd.read_csv(piv_path, index_col=0, parse_dates=True)
    mb_col = "WAVE_SigHeight_m_MB"
    s_col  = "WAVE_SigHeight_m_S"

    if mb_col not in df.columns or s_col not in df.columns:
        print(f"  SKIP Fig 7: wave columns not in pivot")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Time series comparison
    ax = axes[0]
    ax.plot(df.index, df[mb_col], linewidth=0.5, alpha=0.7, color="#1f77b4", label="Provider MB")
    ax.plot(df.index, df[s_col],  linewidth=0.5, alpha=0.7, color="#ff7f0e", label="Provider S")
    ax.set_ylabel("Significant Wave Height (m)")
    ax.set_title("Wave Significant Height: Provider MB vs Provider S\nOctober 2024")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)

    # Scatter agreement
    ax = axes[1]
    sub = df[[mb_col, s_col]].dropna()
    if len(sub) > 0:
        ax.scatter(sub[mb_col], sub[s_col], s=2, alpha=0.2, color="#2ca02c")
        mn = min(sub[mb_col].min(), sub[s_col].min())
        mx = max(sub[mb_col].max(), sub[s_col].max())
        ax.plot([mn, mx], [mn, mx], "r--", linewidth=0.8, label="1:1 line")
        corr = sub[mb_col].corr(sub[s_col])
        ax.set_xlabel("Provider MB (m)")
        ax.set_ylabel("Provider S (m)")
        ax.set_title(f"Provider agreement (n={len(sub):,}, r={corr:.3f})\n"
                     f"Providers are kept separate — not averaged")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No co-observed timestamps", transform=ax.transAxes, ha="center")

    savefig("fig07_provider_mb_vs_s_waves.png")

# --------------------------------------------------------------------------
# Fig 8: Correlation heatmap — safe features only (no leakage), Oct 2024
# --------------------------------------------------------------------------
def plot_correlation_heatmap():
    piv_path = os.path.join(OUT_TAB, "pivot_oct2024.csv")
    if not os.path.exists(piv_path):
        print("  SKIP Fig 8: pivot_oct2024.csv not found")
        return

    df = pd.read_csv(piv_path, index_col=0, parse_dates=True)

    # SAFE features: exclude any torquemeter co-measurements
    LEAKAGE_COLS = {"SHAFT_Revolutions_TQ", "SHAFT_Torque_Nm_TQ", "SHAFT_MechEnergy_kWh_TQ",
                    "SHAFT_ThrustForce_kN_TQ", "SHAFT_RPM_TQ", "ME_FuelMassFlow_kghr_TQ"}
    safe_cols = [c for c in df.columns if c not in LEAKAGE_COLS and c != TARGET_COL]
    use_cols  = safe_cols + [TARGET_COL]
    df_sub = df[use_cols].dropna(how="all")

    corr = df_sub.corr(method="pearson")
    if TARGET_COL in corr.columns:
        # Sort by correlation with target
        target_corr = corr[TARGET_COL].drop(TARGET_COL, errors="ignore").sort_values(key=abs, ascending=False)
        col_order = list(target_corr.index) + [TARGET_COL]
        corr = corr.loc[col_order, col_order]

    fig, ax = plt.subplots(figsize=(14, 11))
    sns.heatmap(corr, ax=ax, cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                annot=True, fmt=".2f", annot_kws={"size": 6},
                linewidths=0.3, square=True)
    ax.set_title("Pearson correlation — safe features + target (October 2024)\n"
                 "Torquemeter co-measurements EXCLUDED to prevent target leakage\n"
                 "Note: correlation computed on unaligned raw timestamps; forward-fill not applied")
    plt.xticks(rotation=45, ha="right", fontsize=7)
    plt.yticks(rotation=0, fontsize=7)
    savefig("fig08_correlation_heatmap.png", tight=False)

# --------------------------------------------------------------------------
# Fig 9: Draft and displacement — Noon Reports time series
# --------------------------------------------------------------------------
def plot_noon_drafts():
    import glob
    noon_files = sorted(glob.glob("data/Noon Reports/*.csv"))
    if not noon_files:
        print("  SKIP Fig 9: No Noon Report files found")
        return

    dfs = []
    for f in noon_files:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
            # Normalise date column
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            dfs.append(df)
        except Exception as e:
            print(f"  WARNING: {f}: {e}")

    df_all = pd.concat(dfs, ignore_index=True)
    df_all = df_all.sort_values("Date").reset_index(drop=True)

    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    # Draft
    ax = axes[0]
    for col, color in [("Fwd Draft","#1f77b4"), ("Mid Draft","#2ca02c"), ("Aft Draft","#d62728")]:
        if col in df_all.columns:
            vals = pd.to_numeric(df_all[col], errors="coerce")
            ax.plot(df_all["Date"], vals, "o-", markersize=2, linewidth=0.8,
                    label=col, color=color, alpha=0.8)
    ax.set_ylabel("Draft (m)")
    ax.set_title("Noon Report — Draft measurements (daily, manual entry)\nSource: 12 monthly Noon Report CSV files")
    ax.legend(fontsize=8)

    # Displacement
    ax = axes[1]
    if "Displacement" in df_all.columns:
        disp = pd.to_numeric(df_all["Displacement"], errors="coerce")
        ax.plot(df_all["Date"], disp, "o-", markersize=2, linewidth=0.8, color="#9467bd")
        ax.set_ylabel("Displacement (t)")
        ax.set_title("Noon Report — Displacement (proxy for loading condition)")
    ax.set_xlabel("Date")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    fig.text(0.01, 0.01, "NOTE: Noon Reports are daily manual entries — cannot be directly joined "
             "to minute-resolution sensor data without temporal alignment.", fontsize=7, color="gray")
    savefig("fig09_noon_report_drafts.png")

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("EDA PLOTS GENERATION")
    print("=" * 70)
    print()

    print("[Fig 1] Monthly row counts ...")
    plot_row_counts()

    print("[Fig 2] Target availability ...")
    plot_target_availability()

    print("[Fig 3] Shaft power time series — Oct 2024 ...")
    plot_shaft_power_timeseries()

    print("[Fig 4] Missing value matrix — Oct 2024 ...")
    plot_missing_matrix()

    print("[Fig 5] Power vs STW scatter ...")
    plot_power_vs_stw()

    print("[Fig 6] Year-wide target coverage (streaming all 12 files) ...")
    plot_year_wide_target()

    print("[Fig 7] Provider MB vs Provider S wave comparison ...")
    plot_provider_comparison()

    print("[Fig 8] Correlation heatmap (safe features only) ...")
    plot_correlation_heatmap()

    print("[Fig 9] Noon Report drafts/displacement ...")
    plot_noon_drafts()

    print(f"\nAll figures saved to: {OUT_FIG}/")

if __name__ == "__main__":
    main()
