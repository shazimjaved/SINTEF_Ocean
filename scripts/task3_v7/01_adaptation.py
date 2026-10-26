"""A: reuse frozen V6 benchmarks. B: conditional chronological adaptation."""
from __future__ import annotations

from common import *
import joblib
import time


def main() -> None:
    prepare()
    dest = OUT / "adaptation"
    dest.mkdir(exist_ok=True)
    if (dest / "completed.json").exists():
        print("PASS: existing V7 A/B experiment preserved")
        return
    a = pd.read_csv(ROOT / "outputs/task3_v6/development_metrics.csv")
    a["experiment"] = "A_reused_V6"
    a["evaluation_status"] = "previously inspected development"
    csv_write(a, OUT / "a_reused_v6_metrics.csv")
    provenance = []
    for path in sorted((ROOT / "outputs/task3_v6/predictions").glob("*.csv.gz")):
        provenance.append({"source_prediction": str(path.relative_to(ROOT)),
                           "sha256": digest(path), "role": "A frozen label-free reference"})
    csv_write(pd.DataFrame(provenance), OUT / "a_prediction_provenance.csv")

    frames = {m: LOAD(m) for m in FIXED_MONTHS + [9, 10]}
    inventory = pd.read_csv(ROOT / "outputs/task3_v6/fit_inventory.csv")
    bspec = json.loads((ROOT / "outputs/task3_v6/models/jan_jun_aug__baselines.json").read_text())
    base = {"mean_kw": bspec["training_mean_kw"], "intercept_kw": bspec["speed_cube_intercept_kw"],
            "cube_kw_per_kn3": bspec["speed_cube_coefficient_kw_per_kn3"]}
    outputs = []
    model_sources = []
    for month in [9, 10]:
        d = frames[month]
        result = output_frame(d)
        result["source_month"] = month
        for key, p in base_predict(d, base).items():
            result[f"fixed_{key}"] = p
        for name in B_MODELS:
            definition = DEFINITIONS[name]
            columns = COLS[definition["group"]]
            path = ROOT / f"outputs/task3_v6/models/jan_jun_aug__{name}.joblib"
            fixed = joblib.load(path)
            last = inventory.loc[(inventory.training_arm == "jan_jun_aug") &
                                 (inventory.candidate == name), "last_training_timestamp"].iloc[0]
            safe = pd.Timestamp(last) < ts(d) - LAG
            p = np.asarray(fixed.predict(d[columns].to_numpy(np.float32)), dtype=np.float64)
            if not safe.all():
                fallback_path = ROOT / f"outputs/task3_v6/models/jan_jun__{name}.joblib"
                fallback = joblib.load(fallback_path)
                p[~safe] = fallback.predict(d.loc[~safe, columns].to_numpy(np.float32))
            result[f"fixed__{name}"] = p
            result[f"fallback_old_model__{name}"] = ~safe.to_numpy()
            result[f"max_training_ts__{name}"] = np.where(safe, last,
                inventory.loc[(inventory.training_arm == "jan_jun") &
                              (inventory.candidate == name), "last_training_timestamp"].iloc[0])
            if month == 9:
                model_sources.append({"candidate": name, "source_model": str(path.relative_to(ROOT)),
                                      "sha256": digest(path), "last_training_label": last,
                                      "latency_rule": "last_training_label < prediction_time-24h",
                                      "old_model_fallback_rows_sep": int((~safe).sum())})
        outputs.append(result)
    combined = pd.concat(outputs, ignore_index=True)
    # Persist only fixed predictions as calibration history. There is no fit
    # using current Sep/Oct labels in either positive fixed model.
    csv_write(combined, dest / "fixed_history.csv.gz")
    csv_write(pd.DataFrame(model_sources), dest / "fixed_model_provenance.csv")
    calibration_columns = [f"fixed__{name}" for name in B_MODELS if name != "B_hgb_broad_full"]
    offsets, persistence, history_mean, ledger = daily_history(
        combined, combined, calibration_columns, base["mean_kw"])
    for col in calibration_columns:
        combined[f"calibrated__{col.removeprefix('fixed__')}"] = combined[col] + offsets[col]
    combined["delayed_persistence"] = persistence
    combined["delayed_history_mean"] = history_mean
    poffset, _, _, positive_ledger = daily_history(
        combined, combined, ["fixed__B_ridge_full"], base["mean_kw"], positive_only=True)
    combined["calibrated_positive_history__B_ridge_full"] = (
        combined["fixed__B_ridge_full"] + poffset["fixed__B_ridge_full"])
    csv_write(ledger, dest / "daily_history_ledger.csv")
    csv_write(positive_ledger, dest / "daily_positive_history_ledger.csv")

    cutoff = pd.Timestamp("2024-09-30T00:00:00Z")
    train = pd.concat([frames[m] for m in FIXED_MONTHS + [9]], ignore_index=True)
    october = frames[10]
    idx_oct = combined.source_month.eq(10)
    fits = []
    for name in B_MODELS:
        selected = training(train, name, cutoff)
        model = FACTORY(DEFINITIONS[name])
        columns = COLS[DEFINITIONS[name]["group"]]
        start = time.perf_counter()
        model.fit(selected[columns].to_numpy(np.float32), selected[TARGET].to_numpy(np.float32))
        elapsed = time.perf_counter() - start
        joblib.dump(model, dest / f"updated_october__{name}.joblib")
        combined[f"updated__{name}"] = np.nan
        combined.loc[idx_oct, f"updated__{name}"] = model.predict(october[columns].to_numpy(np.float32))
        fits.append({"candidate": name, "snapshot_utc": "2024-10-01T00:00:00Z",
                     "label_cutoff_exclusive_utc": cutoff.isoformat(), "train_n": len(selected),
                     "first_label_ts": selected.window_end_utc.min(),
                     "last_label_ts": selected.window_end_utc.max(), "fit_seconds": elapsed,
                     "training_months": "1,2,3,4,5,6,8,9", "feature_n": len(columns)})
        print("B October update", name, len(selected), f"{elapsed:.2f}s", flush=True)
    selected = train.loc[ts(train).lt(cutoff)]
    updated_base = baselines(selected)
    (dest / "updated_baselines.json").write_text(json.dumps(updated_base, indent=2), encoding="utf-8")
    for key, p in base_predict(october, updated_base).items():
        combined[f"updated_{key}"] = np.nan
        combined.loc[idx_oct, f"updated_{key}"] = p
    csv_write(pd.DataFrame(fits), dest / "update_fit_inventory.csv")
    for month, name in [(9, "september"), (10, "october")]:
        part = combined.loc[combined.source_month.eq(month)].copy()
        # History cutoff and size are visible per prediction, even if no labels
        # are present at the prediction timestamp.
        lookup = ledger.set_index("prediction_day_utc")
        key = day_of(part).map(lambda x: x.isoformat())
        part["history_cutoff_exclusive_utc"] = key.map(lookup.history_cutoff_exclusive_utc)
        part["history_n"] = key.map(lookup.history_n)
        part["last_history_ts"] = key.map(lookup.last_history_ts)
        part["history_used"] = key.map(lookup.used_history)
        if month == 9:
            part = part.drop(columns=[c for c in part if c.startswith("updated")])
        csv_write(part, dest / f"predictions_{name}.csv.gz")
    (dest / "completed.json").write_text(json.dumps({"completed": True, "models_fit": 3,
        "assumption": "CONDITIONAL trustworthy target labels and 24h availability"}, indent=2))
    print("PASS: A frozen benchmarks and B conditional adaptation saved")


if __name__ == "__main__":
    main()
