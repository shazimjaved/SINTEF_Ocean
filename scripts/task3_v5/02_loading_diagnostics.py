"""Retrospective loading/speed diagnostics only; no model fit or operational join.

Run: python -X utf8 scripts/task3_v5/02_loading_diagnostics.py
Noon dates lack observation/issue time. Same-date linkage below is exclusively
descriptive and must never be copied into an inference-time feature pipeline.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "task3_v5"
MINUTE = ROOT / "outputs" / "task3" / "data"
NOON = ROOT / "data" / "Noon Reports"
COLS = ["window_end_utc", "SHAFT_MechPower_kW", "STW_kn", "ME_RPM_CAMS",
        "ME_FuelLoad_pct", "ME_ScavAirPressure_bar", "target_n",
        "target_min", "target_negative_n"]
NOON_COLS = ["Fwd Draft", "Mid Draft", "Aft Draft", "Displacement"]
CONDITIONS = ["design", "scantling", "ballast", "heavy_ballast"]
LABEL = "SHAFT_MechPower_kW"
PERIODS = {**{m: "Jan-Jun" for m in range(1, 7)}, 7: "July quarantine",
           8: "August", 9: "Sep-Oct stress", 10: "Sep-Oct stress"}


def load_noon() -> pd.DataFrame:
    parts = []
    for month in PERIODS:
        files = list(NOON.glob(f"N{month:02d}_*_Data_*.csv"))
        assert len(files) == 1, (month, files)
        file = files[0]
        d = pd.read_csv(file, usecols=["Date", *NOON_COLS], low_memory=False)
        d["date"] = pd.to_datetime(d.Date, format="%d/%m/%Y", errors="raise")
        assert len(d) == d.date.nunique(), file
        parts.append(d[["date", *NOON_COLS]].copy())
    out = pd.concat(parts, ignore_index=True)
    assert len(out) == out.date.nunique() == 305
    return out


def load_curves() -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_csv(OUT / "tow_tank_with_psv_tables.csv")
    assert len(c) == 36 and set(c.loading_condition) == set(CONDITIONS)
    ref = c.groupby("loading_condition", as_index=False).first()
    ref["reference_displacement_t_assumed"] = ref.displacement_volume_m3 * 1.025
    return c, ref


def load_month(month: int, noon: pd.DataFrame) -> pd.DataFrame:
    path = MINUTE / f"minute_2024_{month:02d}.csv.gz"
    d = pd.read_csv(path, usecols=COLS, dtype={c: "float32" for c in COLS if c not in
                                              ("window_end_utc", "target_n", "target_negative_n")})
    # A row stamped 00:00 is the minute ending at that instant. Assign its
    # retrospective calendar date from the covered minute, not the next day.
    d["date"] = (pd.to_datetime(d.window_end_utc, utc=True).dt.tz_localize(None)
                 - pd.Timedelta(minutes=1)).dt.normalize()
    d = d.merge(noon, on="date", how="left", validate="many_to_one")
    d["month"] = month
    d["period"] = PERIODS[month]
    d["broader"] = d.target_n.gt(0) & d.STW_kn.ge(3) & d[LABEL].notna()
    d["positive"] = (d.broader & d[LABEL].gt(0) & d.target_min.ge(0)
                     & d.target_negative_n.eq(0))
    d["recorded_zero"] = d.broader & d[LABEL].eq(0) & d.target_negative_n.eq(0)
    return d


def add_provisional_loading(d: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    # Fixed transparent scales are descriptive, not learned from labels.
    # Displacement units in Noon files are absent; tonnes is only an inference.
    x = d[["Fwd Draft", "Aft Draft", "Displacement"]].to_numpy(float)
    states = ref.set_index("loading_condition").loc[CONDITIONS]
    y = states[["fore_draft_m", "aft_draft_m", "reference_displacement_t_assumed"]].to_numpy(float)
    dist = np.sqrt(np.sum(((x[:, None, :] - y[None, :, :]) / np.array([2., 2., 15000.])) ** 2,
                          axis=2))
    nearest = np.argmin(dist, axis=1)
    min_dist = dist[np.arange(len(d)), nearest]
    d["loading_distance"] = min_dist.astype("float32")
    d["loading_reference"] = np.where(min_dist <= 1.0,
                                       np.array(CONDITIONS, dtype=object)[nearest], "not_close")
    return d


def add_reference(d: pd.DataFrame, curves: pd.DataFrame) -> pd.DataFrame:
    d["reference_pdt_kw"] = np.nan
    for name, group in curves.groupby("loading_condition"):
        m = d.loading_reference.eq(name) & d.STW_kn.between(group.speed_kn.min(), group.speed_kn.max())
        if m.any():
            d.loc[m, "reference_pdt_kw"] = np.interp(d.loc[m, "STW_kn"],
                                                       group.speed_kn, group.delivered_propeller_power_kw)
    d["shaft_to_reference_ratio"] = d[LABEL] / d.reference_pdt_kw
    return d


def sample_for_matching(d: pd.DataFrame) -> pd.DataFrame:
    # One positive-power observation per ten-minute UTC block limits serial
    # duplication and makes nearest-neighbour matching cheap on an 8 GB laptop.
    d = d.loc[d.positive & d[["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct",
                               "ME_ScavAirPressure_bar"]].notna().all(axis=1)].copy()
    d["block"] = pd.to_datetime(d.window_end_utc).dt.floor("10min")
    return d.drop_duplicates("block")


def matched_august(train: pd.DataFrame, august: pd.DataFrame) -> pd.DataFrame:
    features = ["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
    scales = np.array([0.5, 5., 5., 0.1])
    tree = cKDTree(train[features].to_numpy(float) / scales)
    distance, indices = tree.query(august[features].to_numpy(float) / scales, workers=1)
    peer = train.iloc[indices].reset_index(drop=True)
    aug = august.reset_index(drop=True)
    r = pd.DataFrame({
        "august_window_end_utc": aug.window_end_utc,
        "reference_window_end_utc": peer.window_end_utc,
        "reference_month": peer.month,
        "normalized_feature_distance": distance,
        "august_power_kw": aug[LABEL], "earlier_power_kw": peer[LABEL],
        "power_difference_august_minus_earlier_kw": aug[LABEL] - peer[LABEL],
        "august_speed_kn": aug.STW_kn, "earlier_speed_kn": peer.STW_kn,
        "august_engine_rpm": aug.ME_RPM_CAMS, "earlier_engine_rpm": peer.ME_RPM_CAMS,
        "august_fuel_load_pct": aug.ME_FuelLoad_pct, "earlier_fuel_load_pct": peer.ME_FuelLoad_pct,
        "august_scav_pressure_bar": aug.ME_ScavAirPressure_bar,
        "earlier_scav_pressure_bar": peer.ME_ScavAirPressure_bar,
        "august_noon_displacement_unit_unspecified": aug.Displacement,
        "earlier_noon_displacement_unit_unspecified": peer.Displacement,
        "august_noon_mid_draft_m": aug["Mid Draft"],
        "earlier_noon_mid_draft_m": peer["Mid Draft"],
        "august_loading_reference": aug.loading_reference,
        "earlier_loading_reference": peer.loading_reference,
    })
    return r


def matched_same_load(august: pd.DataFrame, september: pd.DataFrame) -> pd.DataFrame:
    """September positive to August positive; four label-free match axes."""
    features = ["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
    scales = np.array([0.5, 5., 5., 0.1])
    assert august.loading_reference.eq("scantling").all()
    assert september.loading_reference.eq("scantling").all()
    tree = cKDTree(august[features].to_numpy(float) / scales)
    distance, indices = tree.query(september[features].to_numpy(float) / scales, workers=1)
    ref = august.iloc[indices].reset_index(drop=True)
    query = september.reset_index(drop=True)
    result = pd.DataFrame({"september_window_end_utc": query.window_end_utc,
                           "august_window_end_utc": ref.window_end_utc,
                           "normalized_feature_distance": distance,
                           "september_power_kw": query[LABEL],
                           "august_power_kw": ref[LABEL],
                           "september_minus_august_power_kw": query[LABEL] - ref[LABEL],
                           "september_speed_kn": query.STW_kn,
                           "august_speed_kn": ref.STW_kn,
                           "september_engine_rpm": query.ME_RPM_CAMS,
                           "august_engine_rpm": ref.ME_RPM_CAMS,
                           "september_fuel_load_pct": query.ME_FuelLoad_pct,
                           "august_fuel_load_pct": ref.ME_FuelLoad_pct,
                           "september_scav_pressure_bar": query.ME_ScavAirPressure_bar,
                           "august_scav_pressure_bar": ref.ME_ScavAirPressure_bar,
                           "september_noon_displacement_unit_unspecified": query.Displacement,
                           "august_noon_displacement_unit_unspecified": ref.Displacement,
                           "september_noon_mid_draft_m": query["Mid Draft"],
                           "august_noon_mid_draft_m": ref["Mid Draft"]})
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    noon = load_noon()
    curves, refs = load_curves()
    frames = []
    month_rows = []
    for month in PERIODS:
        d = add_reference(add_provisional_loading(load_month(month, noon), refs), curves)
        month_rows.append(dict(month=month, period=PERIODS[month],
                               minute_rows=len(d), observed_target_minutes=int(d.target_n.gt(0).sum()),
                               forward_minutes=int(d.broader.sum()),
                               positive_minutes=int(d.positive.sum()),
                               recorded_zero_forward_minutes=int(d.recorded_zero.sum()),
                               negative_or_mixed_forward_minutes=int((d.broader & ~d.positive & ~d.recorded_zero).sum()),
                               positive_power_median_kw=d.loc[d.positive, LABEL].median(),
                               positive_speed_median_kn=d.loc[d.positive, "STW_kn"].median(),
                               positive_reference_covered_minutes=int((d.positive & d.reference_pdt_kw.notna()).sum()),
                               noon_displacement_median_unit_unspecified=d.Displacement.median(),
                               noon_mid_draft_median_m=d["Mid Draft"].median()))
        frames.append(d)
        print(f"month {month:02d}: {len(d):,} minute rows, {d.positive.sum():,} positive forward", flush=True)
    all_data = pd.concat(frames, ignore_index=True)
    pd.DataFrame(month_rows).to_csv(OUT / "monthly_loading_power_coverage.csv", index=False)

    # Date-only Noon values are attached retrospectively; each date is one
    # observational unit in the daily summary, not an inference-time feature.
    daily = all_data.groupby(["date", "month", "period"], observed=True).agg(
        noon_fwd_draft_m=("Fwd Draft", "first"),
        noon_mid_draft_m=("Mid Draft", "first"),
        noon_aft_draft_m=("Aft Draft", "first"),
        noon_displacement_unit_unspecified=("Displacement", "first"),
        loading_reference=("loading_reference", "first"),
        loading_distance=("loading_distance", "first"),
        forward_minutes=("broader", "sum"), positive_minutes=("positive", "sum"),
        recorded_zero_minutes=("recorded_zero", "sum"),
    ).reset_index()
    positive = all_data.loc[all_data.positive].copy()
    daily_pos = positive.groupby("date").agg(
        positive_power_median_kw=(LABEL, "median"),
        positive_speed_median_kn=("STW_kn", "median"),
        positive_reference_ratio_median=("shaft_to_reference_ratio", "median"),
        reference_covered_positive_minutes=("reference_pdt_kw", "count"),
    ).reset_index()
    daily = daily.merge(daily_pos, on="date", how="left", validate="one_to_one")
    daily["reference_ratio_eligible"] = daily.reference_covered_positive_minutes.ge(30)
    daily["ratio_for_summary"] = daily.positive_reference_ratio_median.where(
        daily.reference_ratio_eligible)
    daily.to_csv(OUT / "daily_retrospective_loading.csv", index=False)

    # Explicit observed speed and provisional load strata. 0.5 kn bins are
    # useful for overlap checks; low-n bins are shown, never silently dropped.
    subset = all_data.loc[all_data.broader].copy()
    subset["speed_bin_kn"] = np.floor(subset.STW_kn * 2) / 2
    bins = subset.groupby(["period", "month", "loading_reference", "speed_bin_kn"],
                          observed=True).agg(
        n_forward=("broader", "sum"), n_positive=("positive", "sum"),
        n_zero=("recorded_zero", "sum"),
        forward_power_median_kw=(LABEL, "median"),
        forward_power_mean_kw=(LABEL, "mean"),
        forward_speed_median_kn=("STW_kn", "median"),
        reference_pdt_median_kw=("reference_pdt_kw", "median"),
    ).reset_index()
    pos_bins = subset.loc[subset.positive].groupby(
        ["period", "month", "loading_reference", "speed_bin_kn"], observed=True
    ).agg(positive_power_median_kw=(LABEL, "median"),
          positive_power_mean_kw=(LABEL, "mean"),
          positive_reference_ratio_median=("shaft_to_reference_ratio", "median")).reset_index()
    bins = bins.merge(pos_bins, on=["period", "month", "loading_reference", "speed_bin_kn"], how="left")
    bins.to_csv(OUT / "loading_speed_power_bins.csv", index=False)

    # At each speed/condition combination, check whether earlier development
    # and August actually overlap. No claim of causal loading correction.
    prior = bins[bins.month.le(6)].groupby(["loading_reference", "speed_bin_kn"]).agg(
        earlier_months=("month", "nunique"), earlier_positive_n=("n_positive", "sum"),
        earlier_forward_n=("n_forward", "sum")).reset_index()
    aug = bins[bins.month.eq(8)].rename(columns={"n_positive": "august_positive_n",
                                                   "n_forward": "august_forward_n"})
    overlap = aug[["loading_reference", "speed_bin_kn", "august_positive_n", "august_forward_n",
                   "positive_power_median_kw", "forward_power_median_kw"]].merge(
                       prior, on=["loading_reference", "speed_bin_kn"], how="left")
    overlap.to_csv(OUT / "august_earlier_loading_speed_overlap.csv", index=False)

    ratio_summary = daily.groupby(["period", "loading_reference"], observed=True).agg(
        days=("date", "size"), positive_minutes=("positive_minutes", "sum"),
        recorded_zero_minutes=("recorded_zero_minutes", "sum"),
        reference_covered_positive_minutes=("reference_covered_positive_minutes", "sum"),
        reference_days_ge30=("reference_ratio_eligible", "sum"),
        median_of_eligible_daily_reference_ratios=("ratio_for_summary", "median"),
        median_of_daily_power_kw=("positive_power_median_kw", "median"),
        median_of_daily_speed_kn=("positive_speed_median_kn", "median"),
        median_noon_displacement_unit_unspecified=("noon_displacement_unit_unspecified", "median"),
        median_noon_mid_draft_m=("noon_mid_draft_m", "median"),
    ).reset_index()
    ratio_summary.to_csv(OUT / "reference_ratio_loading_summary.csv", index=False)

    # August and September offer the only substantial provisional scantling
    # overlap. Positive and zero counts remain visible in this comparison.
    same_load = bins[bins.month.isin([8, 9]) & bins.loading_reference.eq("scantling")
                     & bins.speed_bin_kn.between(11.0, 13.5)].copy()
    same_load.to_csv(OUT / "august_september_scantling_speed_comparison.csv", index=False)

    within = all_data[(all_data.month.eq(8)) & all_data.positive].copy()
    within["august_segment"] = np.where(within.date.dt.day.le(13), "days_01_13",
                                         np.where(within.date.dt.day.le(27), "days_14_27", "days_28_31"))
    within["speed_bin_kn"] = np.floor(within.STW_kn * 2) / 2
    within = within.groupby(["august_segment", "speed_bin_kn"], observed=True).agg(
        n=(LABEL, "size"), power_median_kw=(LABEL, "median"),
        speed_median_kn=("STW_kn", "median"), engine_rpm_median=("ME_RPM_CAMS", "median"),
        fuel_load_median_pct=("ME_FuelLoad_pct", "median"),
        scav_pressure_median_bar=("ME_ScavAirPressure_bar", "median"),
        noon_displacement_median_unit_unspecified=("Displacement", "median"),
    ).reset_index()
    within.to_csv(OUT / "august_within_month_speed_engine_comparison.csv", index=False)

    # Four independent onboard signals matched retrospectively. The match
    # excludes torquemeter channels and uses positive targets only to define
    # the diagnostic comparison population, never to choose a neighbour.
    earlier = sample_for_matching(all_data.loc[all_data.month.le(6)])
    august = sample_for_matching(all_data.loc[all_data.month.eq(8)])
    pairs = matched_august(earlier, august)
    pairs.to_csv(OUT / "august_earlier_operating_matches.csv.gz", index=False, compression="gzip")
    summary = []
    for limit in [1., 2., 3.]:
        matched = pairs[pairs.normalized_feature_distance.le(limit)]
        summary.append(dict(max_normalized_distance=limit, august_samples=len(pairs),
                            matched_n=len(matched), matched_fraction=len(matched) / len(pairs),
                            distinct_earlier_peers=matched.reference_window_end_utc.nunique(),
                            median_power_difference_kw=matched.power_difference_august_minus_earlier_kw.median(),
                            p10_power_difference_kw=matched.power_difference_august_minus_earlier_kw.quantile(.1),
                            p90_power_difference_kw=matched.power_difference_august_minus_earlier_kw.quantile(.9),
                            median_august_noon_displacement=matched.august_noon_displacement_unit_unspecified.median(),
                            median_earlier_noon_displacement=matched.earlier_noon_displacement_unit_unspecified.median(),
                            same_provisional_loading_fraction=(matched.august_loading_reference == matched.earlier_loading_reference).mean(),
                            median_august_mid_draft_m=matched.august_noon_mid_draft_m.median(),
                            median_earlier_mid_draft_m=matched.earlier_noon_mid_draft_m.median()))
    pd.DataFrame(summary).to_csv(OUT / "august_earlier_match_summary.csv", index=False)

    september = sample_for_matching(all_data.loc[all_data.month.eq(9)
                                             & all_data.loading_reference.eq("scantling")])
    same_load_pairs = matched_same_load(august, september)
    same_load_pairs.to_csv(OUT / "september_august_same_load_matches.csv.gz",
                           index=False, compression="gzip")
    same_load_summary = []
    for limit in [1., 2.]:
        m = same_load_pairs[same_load_pairs.normalized_feature_distance.le(limit)]
        same_load_summary.append(dict(max_normalized_distance=limit,
                                      september_samples=len(same_load_pairs), matched_n=len(m),
                                      matched_fraction=len(m) / len(same_load_pairs),
                                      distinct_august_peers=m.august_window_end_utc.nunique(),
                                      median_september_minus_august_kw=m.september_minus_august_power_kw.median(),
                                      p10_difference_kw=m.september_minus_august_power_kw.quantile(.1),
                                      p90_difference_kw=m.september_minus_august_power_kw.quantile(.9),
                                      median_abs_speed_difference_kn=(m.september_speed_kn - m.august_speed_kn).abs().median(),
                                      median_abs_engine_rpm_difference=(m.september_engine_rpm - m.august_engine_rpm).abs().median(),
                                      median_abs_fuel_load_difference_pct=(m.september_fuel_load_pct - m.august_fuel_load_pct).abs().median(),
                                      median_abs_scav_pressure_difference_bar=(m.september_scav_pressure_bar - m.august_scav_pressure_bar).abs().median(),
                                      median_september_mid_draft_m=m.september_noon_mid_draft_m.median(),
                                      median_august_mid_draft_m=m.august_noon_mid_draft_m.median(),
                                      identical_noon_displacement_fraction=(
                                          m.september_noon_displacement_unit_unspecified ==
                                          m.august_noon_displacement_unit_unspecified).mean()))
    pd.DataFrame(same_load_summary).to_csv(OUT / "september_august_same_load_match_summary.csv",
                                            index=False)

    density = 1.025  # stated seawater-density assumption; not a Noon-file unit label
    scantling_t = 86941 * density
    aug_noon = noon[noon.date.dt.month.eq(8)]
    assert aug_noon.Displacement.nunique() == 1 and aug_noon.Displacement.iloc[0] == 89145
    unit_check = [dict(source="Particulars.xlsx Sheet1 D26 and towing PDF p6",
                       reference="scantling displacement volume", value=86941, unit="m3"),
                  dict(source="assumed seawater density", reference="conversion assumption",
                       value=density, unit="t/m3"),
                  dict(source="calculated", reference="scantling mass at assumed density",
                       value=scantling_t, unit="t"),
                  dict(source="Noon N08 August CSV; 31 same-date values",
                       reference="reported August displacement", value=89145,
                       unit="not stated in source CSV; tonnes inferred, unverified"),
                  dict(source="calculated", reference="August minus converted scantling",
                       value=89145 - scantling_t, unit="t if Noon field is tonnes")]
    pd.DataFrame(unit_check).to_csv(OUT / "displacement_unit_evidence.csv", index=False)

    # Plot only observed data; display counts on figures and separate actual
    # target from theoretical delivered-power curve.
    fig, ax = plt.subplots(figsize=(9, 5.3))
    for period, color in [("Jan-Jun", "#1f77b4"), ("August", "#d62728"),
                          ("Sep-Oct stress", "#9467bd")]:
        x = positive[positive.period.eq(period) & positive.STW_kn.between(11, 16)].copy()
        x["speed_bin_kn"] = np.floor(x.STW_kn * 2) / 2
        g = x.groupby("speed_bin_kn")[LABEL].agg(["median", "size"])
        g = g[g["size"].ge(30)]
        ax.plot(g.index + .25, g["median"], marker="o", label=f"{period} (n={len(x):,})", color=color)
    ax.set(xlabel="Measured speed through water (kn)", ylabel="Observed positive shaft power (kW)",
           title="Observed power by speed; positive scope, 0.5 kn bins (n≥30/bin)")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(OUT / "observed_power_by_speed_period.png", dpi=180)
    plt.close(fig)

    ratio = positive[positive.reference_pdt_kw.notna()
                     & positive.period.isin(["Jan-Jun", "August", "Sep-Oct stress"])]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for period, color in [("Jan-Jun", "#1f77b4"), ("August", "#d62728"),
                          ("Sep-Oct stress", "#9467bd")]:
        x = daily[daily.period.eq(period) & daily.reference_covered_positive_minutes.ge(30)]
        ax.scatter(x.date, x.positive_reference_ratio_median, s=22, alpha=.8,
                   label=f"{period} ({len(x)} days)", color=color)
    ax.axhline(1, color="black", lw=1, ls="--")
    ax.set(xlabel="UTC date (retrospective Noon linkage)",
           ylabel="Daily median shaft kW / reference PDT kW",
           title=f"Diagnostic ratio: {len(ratio):,} in-range positive min; shown dates have ≥30")
    ax.set_xlim(pd.Timestamp(2024, 1, 1), pd.Timestamp(2024, 10, 31))
    ax.legend()
    ax.grid(alpha=.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "daily_reference_ratio_diagnostic.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5.1))
    for month, color in [(8, "#d62728"), (9, "#9467bd")]:
        x = same_load[(same_load.month.eq(month)) & same_load.n_positive.ge(100)]
        ax.plot(x.speed_bin_kn + .25, x.positive_power_median_kw, marker="o",
                label=f"{pd.Timestamp(2024, month, 1):%B}: n={int(x.n_positive.sum()):,} positive; "
                      f"{int(x.n_zero.sum()):,} zeros in shown bins", color=color)
    ax.set(xlabel="Measured speed through water (kn)", ylabel="Observed positive shaft power (kW)",
           title="Provisional scantling load, August vs September (≥100 positive/bin)")
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(OUT / "august_september_same_load_power.png", dpi=180)
    plt.close(fig)
    print(f"PASS: 10 monthly minute files analyzed; {len(pairs):,} August ten-minute matching samples; no models fitted")


if __name__ == "__main__":
    main()
