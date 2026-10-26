"""Audit Task 3 metrics without fitting a model or changing frozen artifacts.

Direct sklearn r2_score is applied to saved validation/test predictions and to
newly saved stress predictions from the already frozen model. Selection-era
candidate predictions were not retained; their R² is recovered by the exact
SSE/SST identity using full-precision stored RMSE and identical August labels,
and marked algebraic rather than misrepresented as direct recomputation.
"""
import hashlib
import json
import runpy
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path("outputs/task3")
TABLES = ROOT / "tables"
ORIGINALS = [
    TABLES / "frozen_selection.json", ROOT / "models/selected_pipeline.joblib",
    TABLES / "test_predictions.csv.gz", TABLES / "validation_selected_predictions.csv",
    TABLES / "validation_model_comparison.csv", TABLES / "stress_metrics.csv",
    TABLES / "test_metrics.csv",
]
COMMON = runpy.run_path("scripts/12_task3_train_validate.py")
load_months, label_mask, speed_cube = (COMMON[x] for x in ["load_months", "label_mask", "speed_cube"])


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def score(y, pred):
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    if len(y) != len(pred) or not np.isfinite(y).all() or not np.isfinite(pred).all():
        raise ValueError("Unaligned or nonfinite labels/predictions")
    pearson = np.nan if np.ptp(pred) <= 1e-10 * max(1, abs(float(pred.mean()))) else float(np.corrcoef(y, pred)[0, 1])
    return {"n": len(y), "mae_kw": float(mean_absolute_error(y, pred)),
            "rmse_kw": float(np.sqrt(mean_squared_error(y, pred))),
            "pearson_r": pearson, "r2_score": float(r2_score(y, pred))}


def consistent(original, computed):
    for key in ["n", "mae_kw", "rmse_kw"]:
        if abs(float(original[key]) - float(computed[key])) > 1e-5:
            return False
    original_r = original["pearson_r"]
    if pd.isna(original_r) and pd.isna(computed["pearson_r"]):
        return True
    return abs(float(original_r) - float(computed["pearson_r"])) < 1e-8


def scope_stats(frame, label):
    target = frame.target_n.gt(0)
    forward = label_mask(frame, broad=True)
    headline = label_mask(frame)
    return {"split": label, "calendar_minutes": len(frame),
            "target_minutes": int(target.sum()), "forward_with_target": int(forward.sum()),
            "headline_minutes": int(headline.sum()),
            "forward_excluded_by_target_rule": int(forward.sum() - headline.sum()),
            "headline_pct_forward": 100 * headline.sum() / forward.sum() if forward.any() else np.nan,
            "headline_pct_calendar": 100 * headline.mean()}


def distribution(frame, label):
    subset = frame.loc[label_mask(frame)]
    return {"split": label, "n": len(subset),
            "target_mean_kw": float(subset.SHAFT_MechPower_kW.mean()),
            "target_std_kw": float(subset.SHAFT_MechPower_kW.std()),
            "target_variance_kw2": float(subset.SHAFT_MechPower_kW.var()),
            "stw_mean_kn": float(subset.STW_kn.mean()),
            "stw_std_kn": float(subset.STW_kn.std()),
            "sog_mean_kn": float(subset.SOG_kn.mean()),
            "relative_wind_mean_kn": float(subset.WIND_RelSpeed_kn.mean()),
            "relative_wind_missing": int(subset.WIND_RelSpeed_kn.isna().sum())}


def main():
    before = {str(p): sha(p) for p in ORIGINALS}
    frozen = json.loads((TABLES / "frozen_selection.json").read_text(encoding="utf-8"))
    bundle = joblib.load(ROOT / "models/selected_pipeline.joblib")
    assert bundle["frozen"] == frozen
    rows = []
    coverage, distributions = [], []

    # January-June and August: labels from the exact compact feature tables.
    train = load_months(list(range(1, 7)))
    august = load_months([8])
    for label, frame in [("jan_jun_train", train), ("august_validation", august)]:
        coverage.append(scope_stats(frame, label))
        distributions.append(distribution(frame, label))
    val_pred = pd.read_csv(TABLES / "validation_selected_predictions.csv")
    aug_head = august.loc[label_mask(august)]
    if not np.array_equal(val_pred.window_end_utc.to_numpy(), aug_head.window_end_utc.to_numpy()):
        raise ValueError("Saved August prediction timestamps do not align with eligible labels")
    if not np.allclose(val_pred.actual_kw.to_numpy(), aug_head.SHAFT_MechPower_kW.to_numpy(), rtol=0, atol=1e-3):
        raise ValueError("Saved August prediction labels disagree with feature-table labels")
    direct_val = score(val_pred.actual_kw, val_pred.predicted_kw)
    rows.append({"period": "august_final_refit", "scope": "headline", "model": "selected_model",
                 "method": "direct_saved_predictions_sklearn", "original_metrics_match": "not_in_original_comparison", **direct_val})

    # Selection-era candidate predictions are unavailable: SSE=n*RMSE². The
    # original full-precision RMSE and this shared August target give R².
    val_original = pd.read_csv(TABLES / "validation_model_comparison.csv")
    y_aug = val_pred.actual_kw.to_numpy(dtype=np.float64)
    sst_aug = np.square(y_aug - y_aug.mean()).sum()
    for original in val_original.itertuples():
        r2 = 1 - int(original.n) * float(original.rmse_kw)**2 / sst_aug
        rows.append({"period": "august_selection", "scope": "headline",
                     "model": f"{original.feature_set}/{original.family}/{original.parameter}",
                     "method": "algebraic_from_original_rmse_no_candidate_predictions",
                     "original_metrics_match": "rmse_identity_only", "n": int(original.n),
                     "mae_kw": float(original.mae_kw), "rmse_kw": float(original.rmse_kw),
                     "pearson_r": original.pearson_r, "r2_score": float(r2)})
    del train, august

    # Save frozen-model stress predictions once, then compute direct sklearn
    # metrics from that saved table. No fit or model selection is invoked.
    stress_path = TABLES / "stress_predictions_metric_audit.csv.gz"
    if stress_path.exists():
        stress_pred = pd.read_csv(stress_path)
    else:
        stress = load_months([9, 10])
        broad = stress.loc[label_mask(stress, broad=True)].copy()
        new = pd.DataFrame({"window_end_utc": broad.window_end_utc,
                            "actual_kw": broad.SHAFT_MechPower_kW,
                            "headline": label_mask(broad).to_numpy(),
                            "selected_model": bundle["pipeline"].predict(
                                broad[bundle["columns"]].to_numpy(dtype=np.float32)),
                            "training_mean": np.full(len(broad), frozen["mean_baseline_kw"]),
                            "speed_cubic": speed_cube(broad, frozen["speed_cube"])})
        new.to_csv(stress_path, index=False, compression="gzip")
        stress_pred = pd.read_csv(stress_path)
        coverage.append(scope_stats(stress, "sep_oct_stress"))
        distributions.append(distribution(stress, "sep_oct_stress"))
    if not any(x["split"] == "sep_oct_stress" for x in coverage):
        stress = load_months([9, 10])
        coverage.append(scope_stats(stress, "sep_oct_stress"))
        distributions.append(distribution(stress, "sep_oct_stress"))
    stress_original = pd.read_csv(TABLES / "stress_metrics.csv")
    for original in stress_original.to_dict("records"):
        subset = stress_pred.loc[stress_pred.headline] if original["scope"] == "headline" else stress_pred
        result = score(subset.actual_kw, subset[original["model"]])
        matches = consistent(original, result)
        if not matches:
            raise ValueError(f"Stress predictions fail original metric reconciliation: {original['scope']}/{original['model']}: {result}")
        rows.append({"period": "sep_oct_stress", "scope": original["scope"],
                     "model": original["model"], "method": "direct_saved_predictions_sklearn",
                     "original_metrics_match": matches, **result})
    del stress

    # December is read only from the ORIGINAL saved predictions for scoring;
    # no model.predict call touches the holdout in this audit.
    december = pd.read_csv(TABLES / "test_predictions.csv.gz")
    december_features = load_months([12])
    dec_broad = december_features.loc[label_mask(december_features, broad=True)]
    if not np.array_equal(december.window_end_utc.to_numpy(), dec_broad.window_end_utc.to_numpy()):
        raise ValueError("Saved December prediction timestamps do not align with eligible labels")
    if not np.allclose(december.SHAFT_MechPower_kW.to_numpy(), dec_broad.SHAFT_MechPower_kW.to_numpy(), rtol=0, atol=1e-3):
        raise ValueError("Saved December labels disagree with feature-table labels")
    if not np.array_equal(december.headline.to_numpy(), label_mask(dec_broad).to_numpy()):
        raise ValueError("Saved December headline flags disagree with frozen rule")
    coverage.append(scope_stats(december_features, "december_holdout"))
    distributions.append(distribution(december_features, "december_holdout"))
    test_original = pd.read_csv(TABLES / "test_metrics.csv")
    pred_col = {"selected_model": "prediction_kw", "training_mean": "mean_baseline_kw",
                "speed_cubic": "speed_cube_kw"}
    for original in test_original.to_dict("records"):
        subset = december.loc[december.headline] if original["scope"] == "headline" else december
        result = score(subset.SHAFT_MechPower_kW, subset[pred_col[original["model"]]])
        matches = consistent(original, result)
        if not matches:
            raise ValueError(f"December predictions fail original metric reconciliation: {original['scope']}/{original['model']}")
        rows.append({"period": "december_holdout", "scope": original["scope"],
                     "model": original["model"], "method": "direct_original_predictions_sklearn",
                     "original_metrics_match": matches, **result})

    # Quarantine coverage is descriptive only; no model scores are calculated.
    for month, label in [(7, "july_quarantine"), (11, "november_quarantine")]:
        frame = load_months([month])
        coverage.append(scope_stats(frame, label))
        distributions.append(distribution(frame, label))
    audit = pd.DataFrame(rows)
    audit.to_csv(TABLES / "metric_science_audit.csv", index=False)
    pd.DataFrame(coverage).to_csv(TABLES / "scope_coverage_audit.csv", index=False)
    pd.DataFrame(distributions).to_csv(TABLES / "split_distribution_audit.csv", index=False)
    after = {str(p): sha(p) for p in ORIGINALS}
    if before != after:
        raise RuntimeError("An original frozen artifact or metric table changed during the audit")
    (TABLES / "frozen_artifact_sha256.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
    direct = audit[audit.method.str.startswith("direct")]
    result = {"direct_rows": len(direct), "algebraic_selection_rows": len(audit)-len(direct),
              "original_files_unchanged": True,
              "december_headline_r2": float(audit.loc[(audit.period == "december_holdout")
                                                   & (audit.scope == "headline")
                                                   & (audit.model == "selected_model"), "r2_score"].iloc[0]),
              "selection_candidate_predictions_available": False}
    (TABLES / "metric_audit_findings.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
