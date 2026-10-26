"""Executable Task 3 temporal, provenance, coverage and split checks."""
import csv
import importlib.util
import json
import runpy
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from channel_config import ANGLE_COLUMNS, COLUMN_TO_QID, COLUMN_TO_SOURCE, DRAFT, LEAKAGE, MODEL_CANDIDATES, TARGET

ROOT = Path("outputs/task3")
DATA = ROOT / "data"
TABLES = ROOT / "tables"
ROWS = []


def check(name, passed, evidence):
    ROWS.append({"id": f"T3Q{len(ROWS)+1:02d}", "claim": name,
                 "status": "PASS" if passed else "FAIL", "evidence": str(evidence)})


def main():
    spec = importlib.util.spec_from_file_location("task3_features", "scripts/11_task3_features.py")
    feature_code = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(feature_code)
    with tempfile.TemporaryDirectory(dir=ROOT) as temp:
        feature_code.RAW = Path(temp)
        rows = [
            ("2024-01-01T00:01:05Z", COLUMN_TO_QID["WIND_TrueSpeed_kn_MB"], 3),
            ("2024-01-01T00:00:30Z", COLUMN_TO_QID["STW_kn"], 7),
            ("2024-01-01T00:00:00Z", COLUMN_TO_QID["STW_kn"], 5),
            ("2024-01-01T00:01:00Z", COLUMN_TO_QID["STW_kn"], 9),
            ("2024-01-01T00:00:05Z", COLUMN_TO_QID["HULL_HeadingTrue_deg"], 350),
            ("2024-01-01T00:00:55Z", COLUMN_TO_QID["HULL_HeadingTrue_deg"], 10),
            ("2024-01-01T00:00:45Z", COLUMN_TO_QID["WIND_TrueSpeed_kn_MB"], 2),
        ]
        with (Path(temp) / "1.csv").open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)
        synthetic, _, _ = feature_code.month_frame(1, {})
    first, second = synthetic.iloc[0], synthetic.iloc[1]
    check("Half-open completed-minute windows exclude observations at or after end",
          first.STW_kn == 6 and second.STW_kn == 9 and first["n__STW_kn"] == 2,
          f"first={first.STW_kn}; second={second.STW_kn}")
    check("Provider latest-time lookup excludes future observation and records age",
          first.WIND_TrueSpeed_kn_MB == 2 and second.WIND_TrueSpeed_kn_MB == 3
          and first["age_s__WIND_TrueSpeed_kn_MB"] == 15
          and second["age_s__WIND_TrueSpeed_kn_MB"] == 55
          and pd.isna(synthetic.iloc[61].WIND_TrueSpeed_kn_MB),
          "first source 00:00:45; second source 00:01:05; stale by 01:02")
    check("Circular mean of 350 and 10 degrees is near zero, not 180",
          first["cos__HULL_HeadingTrue_deg"] > .99
          and abs(first["sin__HULL_HeadingTrue_deg"]) < .01,
          f"sin={first['sin__HULL_HeadingTrue_deg']}; cos={first['cos__HULL_HeadingTrue_deg']}")

    summary = pd.read_csv(TABLES / "feature_build_summary.csv")
    inventory = pd.read_csv("outputs/tables/data_inventory.csv").set_index("file")
    check("All twelve 2024 files built and raw row counts reconcile",
          summary.month.tolist() == list(range(1, 13))
          and int(summary.raw_rows.sum()) == 41079968
          and all(int(summary.loc[summary.month == m, "raw_rows"].iloc[0]) == int(inventory.loc[f"{m}.csv", "row_count"])
                  for m in range(1, 13)),
          f"months={len(summary)}; rows={int(summary.raw_rows.sum())}")
    manifest = json.loads((TABLES / "feature_manifest.json").read_text(encoding="utf-8"))
    check("Manifest uses explicit QIDs and 24 approved candidate channels",
          len(manifest["columns"]) == 36 and len(manifest["candidate_columns"]) == 24
          and set(manifest["candidate_columns"]) == MODEL_CANDIDATES,
          f"mapped={len(manifest['columns'])}; candidates={len(manifest['candidate_columns'])}")
    source_ok = manifest["columns"]["ME_ScavAirPressure_bar"]["source"] == "onboard"
    check("Scavenge-air pressure remains onboard by explicit QID mapping", source_ok,
          manifest["columns"]["ME_ScavAirPressure_bar"])

    target_counts = pd.read_csv("outputs/tables/target_availability.csv").set_index("file")
    total_minutes = 0
    all_schema = None
    leakage_free = True
    age_ok = True
    minute_ok = True
    target_ok = True
    for m in range(1, 13):
        frame = pd.read_csv(DATA / f"minute_2024_{m:02d}.csv.gz")
        total_minutes += len(frame)
        if all_schema is None:
            all_schema = set(frame.columns)
        minute_ok &= (len(frame) == int(summary.loc[summary.month == m, "completed_minutes"].iloc[0])
                      and frame.window_end_utc.is_unique
                      and frame.window_end_utc.is_monotonic_increasing)
        target_ok &= int(frame.target_n.sum()) == int(target_counts.loc[f"{m}.csv", "n_target_obs"])
        leakage_free &= not (set(frame.columns) & (LEAKAGE | DRAFT | {"HULL_WaterDepth_m"}))
        leakage_free &= set(frame.columns) == all_schema
        for col in MODEL_CANDIDATES:
            if COLUMN_TO_SOURCE[col].startswith("provider_"):
                age = frame[f"age_s__{col}"].dropna()
                age_ok &= bool(age.ge(0).all() and age.le(3600).all())
    check("Minute tables have complete calendar grids, ordered unique labels and stable schema",
          minute_ok and total_minutes == 527040, f"minutes={total_minutes}; stable={leakage_free}")
    check("Target reading counts reconcile with prior independent monthly audit", target_ok,
          "All twelve target_n sums equal target_availability.csv")
    check("Export excludes torquemeter proxies, faulty drafts and sparse depth", leakage_free,
          f"columns={len(all_schema)}; forbidden intersection={set(all_schema) & (LEAKAGE | DRAFT)}")
    check("Every retained provider value is no more than 3600 seconds old", age_ok,
          "All 14 provider age columns across twelve monthly tables")

    frozen = json.loads((TABLES / "frozen_selection.json").read_text(encoding="utf-8"))
    bundle = joblib.load(ROOT / "models/selected_pipeline.joblib")
    selected = frozen["selected"]
    check("Frozen chronology preserves Jan-Jun training, August validation, December test",
          frozen["train_months"] == list(range(1, 7)) and frozen["validation_months"] == [8]
          and frozen["test_months"] == [12] and frozen["quarantine_months"] == [7, 11]
          and frozen["coverage_stress_months"] == [9, 10], frozen["train_months"])
    valid_cols = set(all_schema) - {TARGET, "target_n", "target_negative_n", "target_min",
                                    "window_end_utc", "source_month"}
    check("Frozen model uses only candidate transforms and excludes all label fields",
          set(bundle["columns"]).issubset(valid_cols)
          and bundle["columns"] == selected["columns"] and bundle["frozen"] == frozen,
          f"model_columns={len(bundle['columns'])}")
    check("Training-only imputer is inside the saved fitted pipeline",
          any(step.__class__.__name__ == "SimpleImputer" for _, step in bundle["pipeline"].steps),
          str(bundle["pipeline"]))
    training_code = runpy.run_path("scripts/12_task3_train_validate.py")
    train_frame = training_code["load_months"](list(range(1, 7)))
    train_frame = train_frame.loc[training_code["label_mask"](train_frame)]
    train_medians = np.nanmedian(train_frame[bundle["columns"]].to_numpy(dtype=np.float32), axis=0)
    imputer = bundle["pipeline"].steps[0][1]
    check("Saved imputation medians equal eligible January-June medians",
          len(train_frame) == frozen["final_fit_n"]
          and np.allclose(imputer.statistics_, train_medians, rtol=0, atol=1e-5, equal_nan=True),
          f"training rows={len(train_frame)}; columns={len(train_medians)}")
    del train_frame
    comparison = pd.read_csv(TABLES / "validation_model_comparison.csv")
    check("Selection is represented by an August validation row",
          ((comparison.feature_set == selected["feature_set"])
           & (comparison.family == selected["family"])
           & pd.to_numeric(comparison.parameter, errors="coerce").eq(float(selected["parameter"]))).any(),
          selected)
    test_metrics = pd.read_csv(TABLES / "test_metrics.csv")
    predictions = pd.read_csv(TABLES / "test_predictions.csv.gz")
    check("December metrics use only saved one-time holdout predictions",
          len(test_metrics) == 6 and predictions.window_end_utc.is_unique
          and int(predictions.headline.sum()) == int(test_metrics.loc[
              (test_metrics.scope == "headline") & (test_metrics.model == "selected_model"), "n"].iloc[0]),
          f"test rows={len(predictions)}")
    headline = predictions.loc[predictions.headline]
    reported = test_metrics.loc[(test_metrics.scope == "headline")
                                & (test_metrics.model == "selected_model")].iloc[0]
    errors = headline.SHAFT_MechPower_kW - headline.prediction_kw
    check("Saved December predictions independently reproduce reported MAE, RMSE and R",
          abs(float(np.abs(errors).mean()) - reported.mae_kw) < 1e-6
          and abs(float(np.sqrt(np.square(errors).mean())) - reported.rmse_kw) < 1e-6
          and abs(float(headline.SHAFT_MechPower_kW.corr(headline.prediction_kw))
                  - reported.pearson_r) < 1e-9,
          f"n={len(headline)}; MAE={np.abs(errors).mean():.6f}")
    stress_metrics = pd.read_csv(TABLES / "stress_metrics.csv")
    check("Pearson R is undefined for every constant training-mean baseline",
          pd.isna(comparison.loc[comparison.family == "training_mean", "pearson_r"]).all()
          and pd.isna(stress_metrics.loc[stress_metrics.model == "training_mean", "pearson_r"]).all()
          and pd.isna(test_metrics.loc[test_metrics.model == "training_mean", "pearson_r"]).all(),
          "Constant-prediction R cells are blank in all three performance tables")
    pd.DataFrame(ROWS).to_csv(TABLES / "task3_qa.csv", index=False)
    print(pd.DataFrame(ROWS).status.value_counts().to_dict())
    if any(row["status"] == "FAIL" for row in ROWS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
