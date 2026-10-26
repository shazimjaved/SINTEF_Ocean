"""Independent post-freeze scientific QA; no model fitting or prediction."""
import ast
import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
from pypdf import PdfReader
from sklearn.metrics import r2_score

ROOT = Path("outputs/task3")
TABLES = ROOT / "tables"
REPORTS = ROOT / "reports"
ROWS = []
COMMON = runpy.run_path("scripts/12_task3_train_validate.py")
load_months, label_mask = COMMON["load_months"], COMMON["label_mask"]


def check(claim, passed, evidence):
    ROWS.append({"id": f"SA{len(ROWS)+1:02d}", "claim": claim,
                 "status": "PASS" if passed else "FAIL", "evidence": str(evidence)})


def unresolved(claim, evidence):
    ROWS.append({"id": f"SA{len(ROWS)+1:02d}", "claim": claim,
                 "status": "UNRESOLVED", "evidence": str(evidence)})


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def row(metric, period, scope, model):
    return metric[(metric.period == period) & (metric.scope == scope)
                  & (metric.model == model)].iloc[0]


def main():
    metric = pd.read_csv(TABLES / "metric_science_audit.csv")
    original_test = pd.read_csv(TABLES / "test_metrics.csv")
    saved_test = pd.read_csv(TABLES / "test_predictions.csv.gz")
    saved_aug = pd.read_csv(TABLES / "validation_selected_predictions.csv")
    stress = pd.read_csv(TABLES / "stress_predictions_metric_audit.csv.gz")
    expected_hashes = json.loads((TABLES / "frozen_artifact_sha256.json").read_text(encoding="utf-8"))
    actual_hashes = {path: digest(path) for path in expected_hashes}
    check("Frozen selection, model, original predictions and metric tables retain audited SHA256",
          expected_hashes == actual_hashes, f"verified={len(actual_hashes)} original artifacts")

    val = row(metric, "august_final_refit", "headline", "selected_model")
    direct_val_r2 = r2_score(saved_aug.actual_kw, saved_aug.predicted_kw)
    check("Exact sklearn R² recomputation from saved August final-fit predictions",
          abs(direct_val_r2 - val.r2_score) < 1e-12,
          f"r2_score={direct_val_r2:.12f}")
    selection = metric[metric.period == "august_selection"]
    august_sst = np.square(saved_aug.actual_kw.to_numpy(dtype=np.float64)
                           - saved_aug.actual_kw.mean()).sum()
    recovered = (1 - selection.n.to_numpy(dtype=np.float64)
                 * np.square(selection.rmse_kw.to_numpy(dtype=np.float64)) / august_sst)
    check("All historical August candidate R² rows obey disclosed SSE/SST recovery identity",
          len(selection) == 14 and np.allclose(recovered, selection.r2_score, rtol=0, atol=1e-12)
          and selection.method.eq("algebraic_from_original_rmse_no_candidate_predictions").all(),
          f"selection rows={len(selection)}; individual candidate predictions unavailable")
    test_rows = metric[metric.period == "december_holdout"]
    mapping = {"selected_model": "prediction_kw", "training_mean": "mean_baseline_kw",
               "speed_cubic": "speed_cube_kw"}
    direct_test = True
    original_match = True
    for audit_row in test_rows.itertuples():
        part = saved_test[saved_test.headline] if audit_row.scope == "headline" else saved_test
        value = r2_score(part.SHAFT_MechPower_kW, part[mapping[audit_row.model]])
        direct_test &= abs(value-audit_row.r2_score) < 1e-12
        old = original_test[(original_test.scope == audit_row.scope)
                            & (original_test.model == audit_row.model)].iloc[0]
        original_match &= (abs(old.mae_kw-audit_row.mae_kw) < 1e-5
                           and abs(old.rmse_kw-audit_row.rmse_kw) < 1e-5)
    check("Exact sklearn R² for every December model and both scopes uses original predictions",
          direct_test and len(test_rows) == 6, f"rows={len(test_rows)}")
    check("Original December MAE/RMSE and predictions remain numerically consistent",
          original_match and test_rows.original_metrics_match.astype(str).eq("True").all(),
          "All six original rows reconciled within 1e-5 kW")

    stress_rows = metric[metric.period == "sep_oct_stress"]
    direct_stress = True
    for audit_row in stress_rows.itertuples():
        part = stress[stress.headline] if audit_row.scope == "headline" else stress
        direct_stress &= abs(r2_score(part.actual_kw, part[audit_row.model])-audit_row.r2_score) < 1e-12
    check("Exact sklearn R² for every stress model and both scopes uses saved frozen-model inference",
          direct_stress and len(stress_rows) == 6 and stress_rows.original_metrics_match.astype(str).eq("True").all(),
          f"rows={len(stress_rows)}")
    dec = row(metric, "december_holdout", "headline", "selected_model")
    check("Pearson r and R² are separate, non-interchangeable columns",
          "pearson_r" in metric and "r2_score" in metric
          and abs(dec.pearson_r-dec.r2_score) > 1
          and abs(dec.pearson_r**2-dec.r2_score) > 1,
          f"Pearson r={dec.pearson_r:.6f}; R²={dec.r2_score:.6f}")

    august = load_months([8])
    aug_eligible = august.loc[label_mask(august)]
    dec_features = load_months([12])
    dec_eligible = dec_features.loc[label_mask(dec_features, broad=True)]
    check("Saved August and December predictions align one-to-one with eligible timestamped labels",
          saved_aug.window_end_utc.is_unique and saved_test.window_end_utc.is_unique
          and np.array_equal(saved_aug.window_end_utc.to_numpy(), aug_eligible.window_end_utc.to_numpy())
          and np.array_equal(saved_test.window_end_utc.to_numpy(), dec_eligible.window_end_utc.to_numpy())
          and np.allclose(saved_aug.actual_kw, aug_eligible.SHAFT_MechPower_kW, rtol=0, atol=.001)
          and np.allclose(saved_test.SHAFT_MechPower_kW, dec_eligible.SHAFT_MechPower_kW, rtol=0, atol=.001),
          f"August={len(saved_aug)}; December={len(saved_test)}")
    stress_features = load_months([9, 10])
    stress_eligible = stress_features.loc[label_mask(stress_features, broad=True)]
    check("Saved stress predictions align one-to-one with eligible timestamped labels",
          stress.window_end_utc.is_unique
          and np.array_equal(stress.window_end_utc.to_numpy(), stress_eligible.window_end_utc.to_numpy())
          and np.allclose(stress.actual_kw, stress_eligible.SHAFT_MechPower_kW, rtol=0, atol=.001),
          f"stress={len(stress)}")

    coverage = pd.read_csv(TABLES / "scope_coverage_audit.csv").set_index("split")
    matched = True
    for name, frame in [("august_validation", august), ("sep_oct_stress", stress_features),
                        ("december_holdout", dec_features)]:
        item = coverage.loc[name]
        broad = int(label_mask(frame, broad=True).sum())
        head = int(label_mask(frame).sum())
        matched &= (broad == int(item.forward_with_target)
                    and head == int(item.headline_minutes)
                    and broad-head == int(item.forward_excluded_by_target_rule))
    check("Target-conditional headline and broader counts independently reconcile by split",
          matched and int(coverage.loc["december_holdout", "headline_minutes"]) == 39270
          and int(coverage.loc["sep_oct_stress", "headline_minutes"]) == 38517,
          "August, stress and December masks recomputed from saved minute tables")
    check("Headline eligibility depends on unseen target fields and is identified as retrospective",
          "target_min" in COMMON["label_mask"].__code__.co_names
          and "target_negative_n" in COMMON["label_mask"].__code__.co_names,
          "The rule requires target minimum and negative-reading count")

    bins = pd.read_csv(TABLES / "diagnostic_bin_coverage.csv").set_index("condition")
    audited = pd.read_csv(TABLES / "test_operating_condition_error_audited.csv")
    daily = pd.read_csv(TABLES / "test_daily_error_audited.csv")
    speed = pd.read_csv(TABLES / "test_speed_error_audited.csv")
    check("Every diagnostic grouping accounts for all December headline observations",
          bins.binned_n.eq(39270).all() and int(daily.n.sum()) == 39270
          and int(speed.n.sum()) == 39270
          and audited.groupby("condition").n.sum().eq(39270).all(),
          "Relative wind, turn, SOG, STW and daily totals each equal 39,270")
    check("Relative-wind missing 94 and high-turn-rate n=8 are explicit and disclosed",
          int(bins.loc["relative_wind_kn", "missing_bin_n"]) == 94
          and int(bins.loc["absolute_turn_degmin", "small_high_turn_bin_n"]) == 8
          and int(audited.loc[(audited.condition == "relative_wind_kn")
                              & (audited.bin == "Missing"), "n"].iloc[0]) == 94,
          "Missing relative wind=94; highest turn-rate bin=8")

    frozen = json.loads((TABLES / "frozen_selection.json").read_text(encoding="utf-8"))
    no_fit = True
    for name in ["17_task3_metric_science_audit.py", "18_task3_diagnostic_figures.py",
                 "19_task3_academic_report.py", "20_task3_scientific_qa.py"]:
        tree = ast.parse((Path("scripts") / name).read_text(encoding="utf-8"))
        no_fit &= not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                          and node.func.attr in {"fit", "fit_transform", "partial_fit"}
                          for node in ast.walk(tree))
    check("Post-freeze audit scripts contain no fitting calls and frozen split excludes December from training",
          no_fit and frozen["train_months"] == [1,2,3,4,5,6]
          and frozen["validation_months"] == [8] and frozen["test_months"] == [12]
          and expected_hashes == actual_hashes,
          "Audit code has no fit/partial_fit call; original model and selection hashes unchanged")

    pdf = REPORTS / "task3_academic_report.pdf"
    md = (REPORTS / "task3_academic_report.md").read_text(encoding="utf-8")
    check("Academic PDF and paginated Markdown contain exactly 46 pages",
          len(PdfReader(str(pdf)).pages) == 46
          and md.count('style="page-break-after: always;"') == 45,
          "PDF=46 pages; Markdown=46 numbered sections with 45 page breaks")
    check("Academic report separates Pearson r and R² and omits internal script paths",
          "Pearson r" in md and "R²" in md
          and "scripts/" not in md and "outputs/" not in md
          and "agent" not in md.lower(),
          "Metric names distinct; internal script paths and agent history absent")
    unresolved("Direct sklearn R² for historical August candidate fits cannot be recomputed",
               "Individual selection-era candidate predictions and fitted candidate objects were not saved; algebraic R² from exact RMSE and common labels is disclosed")

    out = TABLES / "task3_scientific_qa.csv"
    pd.DataFrame(ROWS).to_csv(out, index=False)
    counts = pd.DataFrame(ROWS).status.value_counts().to_dict()
    print(counts)
    if counts.get("FAIL", 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
