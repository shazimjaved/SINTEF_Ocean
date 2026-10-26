"""Observed October speed-power profile and a separate illustrative cubic law.

No target-defined 'transit' class or causal explanation of the decline is
asserted. Fig05b is retained on disk as superseded; this writes fig05c.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TABLES = Path("outputs/tables")
FIGURES = Path("outputs/figures")
PIVOT = TABLES / "pivot_oct2024.csv"


def main():
    df = pd.read_csv(PIVOT, index_col=0, parse_dates=True,
                     usecols=["ts_parsed", "SHAFT_MechPower_kW", "STW_kn"])
    minute = df.resample("1min").mean()
    minute.index = minute.index + pd.Timedelta(minutes=1)
    pair = minute.dropna()
    valid = pair[(pair.STW_kn >= 0) & (pair.SHAFT_MechPower_kW >= 0)].copy()

    # Empirical bin summaries are shown only where at least 30 minutes occur.
    edges = np.arange(0, 15.5, .5)
    valid["speed_bin"] = pd.cut(valid.STW_kn, edges, right=False)
    grouped = valid.groupby("speed_bin", observed=False).SHAFT_MechPower_kW
    stats = grouped.agg(n="size", median_kw="median", q25_kw=lambda s: s.quantile(.25),
                        q75_kw=lambda s: s.quantile(.75)).reset_index()
    stats["speed_mid_kn"] = stats.speed_bin.map(lambda b: (b.left + b.right) / 2).astype(float)
    stats["speed_bin"] = stats.speed_bin.astype(str)
    stats.to_csv(TABLES / "speed_power_bins_oct2024.csv", index=False)

    # Preserve the earlier polynomial as an audit diagnostic. Its behaviour is
    # not treated as a physical ship resistance curve.
    all_positive = pair[(pair.STW_kn > 0) & (pair.SHAFT_MechPower_kW > 0)]
    polynomial = np.poly1d(np.polyfit(all_positive.STW_kn, all_positive.SHAFT_MechPower_kW, 3))
    diag = pd.DataFrame([{
        "n_paired_minutes": len(pair), "n_positive_speed_and_power": len(all_positive),
        "polynomial_at_7kn_kw": polynomial(7), "polynomial_at_10kn_kw": polynomial(10),
        "polynomial_at_14kn_kw": polynomial(14),
        "interpretation": "unconstrained descriptive cubic; not a physical or causal curve",
    }])
    diag.to_csv(TABLES / "speed_power_polynomial_diagnostic.csv", index=False)

    shown = stats[stats.n >= 30]
    near12 = valid[valid.STW_kn.between(11.5, 12.5)].SHAFT_MechPower_kW
    anchor = near12.median()
    if len(near12) < 30 or not np.isfinite(anchor) or anchor <= 0:
        raise ValueError("Insufficient observations for an illustrative 12-kn anchor")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.errorbar(shown.speed_mid_kn, shown.median_kw,
                 yerr=[shown.median_kw - shown.q25_kw, shown.q75_kw - shown.median_kw],
                 fmt="o", color="#2a7f62", capsize=2,
                 label="Observed median and middle 50%")
    ax1.set(xlabel="Speed through water (kn)", ylabel="Shaft power (kW)",
            title="Observed October; nonnegative speed/power; 0.5-kn bins with ≥30 minutes")
    ax1.legend()
    ax1.grid(alpha=.2)
    x = np.linspace(0, 15, 150)
    ax2.plot(x, anchor * (x / 12)**3, color="#38598a", label="Illustrative P ∝ v³")
    ax2.scatter([12], [anchor], color="black", zorder=3,
                label=f"12-kn observed anchor (n={len(near12):,})")
    ax2.set(xlabel="Speed through water (kn)", ylabel="Scaled power (kW)",
            title="Theoretical cubic shape; fixed coefficient")
    ax2.legend()
    ax2.grid(alpha=.2)
    fig.suptitle("Observed association and physical heuristic are separate; loading and conditions are uncontrolled")
    fig.text(.02, .01, "The October empirical curve is not a vessel-wide speed-power law. "
             "The earlier unrestricted cubic falls from 7 to 10 kn even after the reported regime filter.",
             fontsize=8)
    plt.tight_layout(rect=(0, .05, 1, .95))
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "fig05c_observed_vs_theory.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"October paired minutes={len(pair):,}; positive pairs={len(all_positive):,}; "
          f"diagnostic P(7)={polynomial(7):.1f}, P(10)={polynomial(10):.1f} kW")


if __name__ == "__main__":
    main()
