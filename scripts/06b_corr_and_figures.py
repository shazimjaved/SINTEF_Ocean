"""Render corrected October coverage, overlap and correlation figures.

Run 06_temporal_alignment.py first. Earlier b-suffix figures remain on disk
as superseded artifacts and are not written by this script.
"""

from pathlib import Path
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from channel_config import ENVIRONMENTAL, TARGET

TABLES = Path("outputs/tables")
FIGURES = Path("outputs/figures")
FIGURES.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "figure.dpi": 120})


def save(name):
    plt.tight_layout()
    plt.savefig(FIGURES / name, dpi=140, bbox_inches="tight")
    plt.close()
    print("Saved", name)


def target_density():
    d = pd.read_csv(TABLES / "overlap_stats_yearwide.csv")
    x = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - .18, d.n_target_obs / 1000, .36, label="Recorded target readings")
    ax.bar(x + .18, d.expected_at_nominal_15sec / 1000, .36,
           label="Calendar × nominal 15-second rate", color="#aec7e8")
    ax.set_xticks(x, d.month)
    ax.set_ylabel("Readings (thousands)")
    ax.set_title("2024 target observation-count density; this does not identify the cause of gaps")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, .5), frameon=False)
    for i, pct in enumerate(d.pct_of_nominal_15sec):
        ax.text(i - .18, d.n_target_obs.iloc[i] / 1000 + 1, f"{pct:.1f}%",
                ha="center", fontsize=7)
    save("fig02c_target_density.png")


def aligned_coverage():
    d = pd.read_csv(TABLES / "alignment_summary.csv").sort_values("pct_coverage_aligned")
    colors = d.feature_role.map({
        "target": "#c23b42", "candidate": "#2a7f62",
        "excluded_torquemeter": "#8e69ad",
        "excluded_constant_zero_draft": "#999999",
        "excluded_no_october_overlap": "#999999",
    })
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.barh(d.sensor, d.pct_coverage_aligned, color=colors)
    ax.set_xlabel("% of 44,640 completed-minute intervals with an aligned value")
    ax.set_title("October 2024 completed-minute alignment\n"
                 "Green=candidate; red=target; purple=torquemeter exclusion; grey=other exclusion")
    save("fig04c_aligned_coverage.png")


def target_correlation():
    d = pd.read_csv(TABLES / "correlation_target_evidence.csv").sort_values("pearson_r_october")
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = ["#5186b8" if s in {"provider_mb", "provider_s"} else "#2a7f62"
              for s in d.source_group]
    ax.barh(d.predictor, d.pearson_r_october, color=colors)
    ax.axvline(0, color="black", linewidth=.7)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("Pearson r with shaft power on aligned October completed minutes")
    ax.set_title("October descriptive Pearson r; circular angles, draft and torquemeter inputs excluded\n"
                 "Blue provider values reuse hourly sources; paired counts are in correlation_target_evidence.csv")
    save("fig08c_target_correlation.png")


def daily_counts():
    d = pd.read_csv(TABLES / "coverage_per_qid_oct2024.csv", index_col=0)
    summary = pd.read_csv(TABLES / "alignment_summary.csv").set_index("sensor")
    keep = [TARGET] + summary[summary.feature_role == "candidate"].index.tolist()
    keep = list(dict.fromkeys(keep))
    values = d[keep].T
    fig, ax = plt.subplots(figsize=(13, 7))
    im = ax.imshow(values, aspect="auto", cmap="Blues")
    ax.set_yticks(range(len(keep)), keep, fontsize=7)
    ax.set_xticks(range(31), range(1, 32), fontsize=7)
    ax.set_xlabel("October day")
    ax.set_title("Raw observation counts per day; colour scale spans different sensor sampling rates")
    fig.colorbar(im, ax=ax, shrink=.75, label="Raw readings")
    save("fig10b_daily_counts.png")


def overlap():
    d = pd.read_csv(TABLES / "overlap_stats_oct2024.csv")
    d = d[d.feature_role.isin(["candidate", "excluded_no_october_overlap"])]
    d = d.sort_values("n_coobserved_completed_minutes")
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = ["#5186b8" if s in {"provider_mb", "provider_s"} else
              "#999999" if r == "excluded_no_october_overlap" else "#2a7f62"
              for s, r in zip(d.source_group, d.feature_role)]
    ax.barh(d.predictor, d.n_coobserved_completed_minutes, color=colors)
    ax.set_xlabel("Completed-minute pairs with target (October 2024)")
    ax.set_title("October target overlap after alignment; provider pairs reuse hourly readings\n"
                 "Blue=provider; green=onboard candidate; grey=excluded water depth")
    save("fig11b_target_overlap.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", choices=["all", "02c"], default="all",
                        help="Regenerate all current figures or only Figure 02c")
    choice = parser.parse_args().figure
    target_density()
    if choice == "all":
        aligned_coverage()
        target_correlation()
        daily_counts()
        overlap()
