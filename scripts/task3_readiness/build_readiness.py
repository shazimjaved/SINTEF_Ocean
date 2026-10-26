"""Build the internal frozen-evidence index and notebook; never fit models."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import json
import pandas as pd
import nbformat

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/task3_readiness"
NOTEBOOK = ROOT / "notebooks/task3_frozen_evidence.ipynb"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


FIGURES = [
    ("F3_FOLDS", "outputs/task3_v3/models/v3_label_free_fold_metrics.png", "A", "Headline denotes the retrospective positive-target subset. Broader-forward includes recorded zeros and negative/mixed labels. Chronological development folds; no reliable all-regime generalization. R2 is distinct from Pearson r."),
    ("F4_FAMILIES", "outputs/task3_v4/models/v4_family_comparison.png", "A", "Five previously tested model families with the same extended onboard inputs. Headline is a retrospective positive-target subset; broader-forward retains uncertain zeros. These development results do not select a new winner."),
    ("F5_PHYSICS", "outputs/task3_v5/tow_tank_with_psv_curves.png", "D", "Physical reference only: calm-water, clean-hull corrected delivered propeller power, not validated measured shaft power. Loading comparisons are retrospective; incompatible engine references and unknown Noon timing prevent automatic correction."),
    ("F6_HISTORY", "outputs/task3_v6/figures/v6_mae_training_history.png", "A", "Fixed historical model definitions before/after adding August. Positive panels are retrospective target-conditioned subsets; broader-forward panels preserve zero/negative truths. Previously inspected September/October development; no universal winner."),
    ("F6_DAILY", "outputs/task3_v6/figures/v6_daily_ridge_stability.png", "A", "Daily Ridge error; plotted days require at least 30 observed labels. Positive panels are retrospective subsets; broader-forward includes recorded-zero states. All days and missing-truth coverage remain in the tables."),
    ("F6_ZERO", "outputs/task3_v6/figures/v6_zero_state_error.png", "A", "Retrospective recorded-zero diagnostic. Zeros are observed and quality-uncertain, not confirmed missing or physical disengagement. October has only 12 zero observations; it cannot support a reliable zero-state performance claim."),
    ("F7_ADAPT", "outputs/task3_v7/figures/b_scenario_mae.png", "B", "Fixed and conditional label-assisted scenarios use different information. Assisted methods assume trustworthy labels, at least 24h delay and daily refresh. Positive panels are retrospective subsets. Match assisted methods against delayed persistence/history mean; retain September transition failures."),
    ("F7_BLOCKS", "outputs/task3_v7/figures/c_24h_block_stability.png", "C", "All scheduled original 24h gap blocks remain present; blank errors mean unscoreable forward truth. This retrospective reconstruction simulation assumes independent inputs survive and historical labels meet the stated delay. Zero states remain uncertain."),
    ("F7_DURATION", "outputs/task3_v7/figures/c_gap_duration_mae.png", "C", "Original V7 durations use different calendar/operating samples, so the curve is not a causal gap-duration effect. Positive panels are retrospective target-conditioned subsets. Historical-label availability and independent-input survival are conditional."),
    ("F8_PREFIX", "outputs/task3_v8/figures/paired_prefix_comparison.png", "C-paired", "Paired anchors, common 24h embargo and identical prediction prefixes. Different horizons contain different operating minutes and missing-truth coverage; no causal duration claim. Retrospective development simulation; persistence outperforms tested calibration broadly, but still fails transitions."),
    ("F8_TRANSITIONS", "outputs/task3_v8/figures/transition_failure_ablation.png", "B/C", "Four previously inspected failure cases, not a representative accuracy sample. Retrospective label-state diagnostics; early-fold safeguards cannot certify current state. Accepted August zero errors and positive recovery errors remain included."),
    ("F8_RISK", "outputs/task3_v8/figures/abstention_false_confidence.png", "B/C", "Historical-risk acceptance is not a confidence guarantee. Accepted-zero groups are retrospective target-conditioned subsets: all their errors exceed the early q95 reference. Accepted-positive accuracy alone would conceal severe failures."),
]


def commands():
    rows = [
        ("VERIFY", "python -X utf8 -B scripts/task3_readiness/verify_saved_outputs.py", "saved_output_only", False, "Current consolidated hashes, chronology, ledgers, metrics, scopes and coverage"),
        ("NOTEBOOK", "python -X utf8 -B scripts/task3_readiness/run_notebook.py", "saved_output_only", False, "Execute actual notebook code cells in a fresh Python process; validate ipynb; measure CPU/RAM"),
        ("NOTEBOOK_ENV", "python -m pip install -r scripts/task3_readiness/requirements.txt", "environment_setup", False, "Pinned available verification dependencies; installation not performed by verifier"),
        ("JUPYTER_ENV", "python -m pip install -r scripts/task3_readiness/requirements-jupyter.txt", "optional_environment_setup", False, "Standard Jupyter extras; unavailable from package index during this session"),
    ]
    rebuilds = [("V1_FEATURES", "scripts/11_task3_features.py", False), ("V1_FIT", "scripts/12_task3_train_validate.py", True),
                ("V1_EVAL", "scripts/13_task3_evaluate.py", False), ("V2_FITS", "scripts/task3_v2/07_walkforward_experiments.py", True),
                ("V3_FITS", "scripts/task3_v3/04_label_free_temporal_models.py", True), ("V4_FITS", "scripts/task3_v4/04_boosting_development.py", True),
                ("V5_REFERENCES", "scripts/task3_v5/01_physical_references.py", False), ("V6_FITS", "scripts/task3_v6/01_run_development.py", True),
                ("V7_ADAPT", "scripts/task3_v7/01_adaptation.py", True), ("V7_GAPS", "scripts/task3_v7/02_reconstruction.py", True),
                ("V7_QA", "scripts/task3_v7/04_qa.py", True), ("V8_PAIRED", "scripts/task3_v8/03_paired_reconstruction.py", True),
                ("V8_QA", "scripts/task3_v8/05_qa.py", True)]
    for name, script, fit in rebuilds:
        rows.append((name, "python -X utf8 -B " + script, "historical_fresh_copy_only_DO_NOT_RUN_HERE", fit,
                     "Provenance/rebuild reference only; writes historical output paths; QA can contain sentinel fits"))
    return pd.DataFrame(rows, columns=["command_id", "command_from_project_root", "mode", "can_fit_models", "purpose"])


def create_notebook():
    nbf = nbformat.v4
    cells = [nbf.new_markdown_cell(
        "# Task 3 frozen evidence: implementation notebook\n\n"
        "Replays saved-output checks and displays retained technical comparisons. "
        "No training, model selection, relabelling or report generation. Target: recorded completed-minute shaft power in kW. "
        "Recorded zeros remain observed and quality-uncertain. Positive-only and zero-excluded scores are retrospective subsets. "
        "The supported local runner executes these Python cells in a fresh process; standard Jupyter additionally needs ipykernel."),
        nbf.new_code_cell("from pathlib import Path\nimport sys, os\n"
            "ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'scripts/task3_readiness/verify_saved_outputs.py').exists())\n"
            "sys.path.insert(0, str(ROOT / 'scripts/task3_readiness'))\n"
            "from verify_saved_outputs import run_verification\nimport pandas as pd\n"
            "print('Project:', ROOT.name)\n"),
        nbf.new_code_cell("checks = run_verification(ROOT / 'outputs/task3_readiness/notebook_verification')\n"
            "print(checks[['check_id','status']].to_string(index=False))\n"
            "assert checks.status.eq('PASS').all(), 'Saved-output verification failed'"),
        nbf.new_markdown_cell("## Information scenarios and scope\n"
            "Compare methods within their stated information scenario. Past target labels and synchronous same-package physics "
            "are additional information, not independent-sensor prediction. All later periods have been inspected. "
            "Original December results are replayed only to verify the historical frozen evaluation."),
        nbf.new_code_cell("scenarios = pd.read_csv(ROOT / 'outputs/task3_readiness/scenario_comparisons.csv')\n"
            "print(scenarios[['scenario','retained_reference','matched_baselines','defensible_interpretation']].to_string(index=False))\n"
            "policy = pd.read_csv(ROOT / 'outputs/task3_target_decision/scope_quality_decisions.csv')\n"
            "print(policy[['topic','policy']].to_string(index=False))"),
        nbf.new_code_cell("panel = pd.read_csv(ROOT / 'outputs/task3_target_decision/key_scope_comparisons.csv')\n"
            "print(panel[['experiment','period','method','scope','n','mae_kw','rmse_kw','r2_score','pearson_r','bias_actual_minus_pred_kw','scored_scope_coverage_of_eligible']].to_string(index=False))"),
        nbf.new_markdown_cell("## Retained figures and authoritative captions\n"
            "Captions below qualify the original panels. The historical PNGs are preserved; use them with these captions. "
            "The complete reviewed set and excluded archival figures are in figure_captions.csv."),
        nbf.new_code_cell("figures = pd.read_csv(ROOT / 'outputs/task3_readiness/figure_captions.csv')\n"
            "def show_figure(figure_id):\n"
            "    row = figures[figures.figure_id.eq(figure_id)].iloc[0]\n"
            "    print(row.authoritative_caption)\n"
            "    path = str(ROOT / row.path)\n"
            "    if '_capture_png' in globals():\n"
            "        _capture_png(path)\n"
            "    else:\n"
            "        from IPython.display import display, Image\n"
            "        display(Image(filename=path))\n"
            "for figure_id in ['F6_HISTORY','F7_ADAPT','F8_PREFIX','F8_RISK']:\n"
            "    show_figure(figure_id)"),
        nbf.new_code_cell("index = pd.read_csv(ROOT / 'outputs/task3_readiness/artifact_index.csv')\n"
            "print(index.groupby(['version','role'], dropna=False).size().to_string())\n"
            "print('Verification and notebook outputs are internal implementation evidence.')\n"
            "print('Runtime/RAM measurements are saved by run_notebook.py in notebook_execution.json.')"),
        nbf.new_markdown_cell("## Technical limits\n"
            "Source-level physical validity, zero/status conventions and actual delayed-label availability remain unresolved. "
            "No universal all-regime model is promoted. Historical training/feature-build scripts are indexed for a fresh copy "
            "but are not executed here. This notebook reproduces frozen evidence; it does not re-estimate historical weights.")]
    notebook = nbf.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                                    "language_info": {"name": "python", "version": "3.11.0"}})
    nbformat.validate(notebook)
    NOTEBOOK.parent.mkdir(exist_ok=True)
    nbformat.write(notebook, NOTEBOOK)


def metadata(path):
    p = path.as_posix()
    version = next((f"V{i}" for i in range(2, 9) if f"task3_v{i}/" in p), "V1" if "outputs/task3/" in p else "shared")
    if "source_audit" in p: version = "source_audit"
    if "target_decision" in p: version = "target_decision"
    suffix = path.suffix.lower()
    if suffix == ".joblib": role = "saved_model"
    elif "manifest" in p or "provenance" in p or "inventory" in p: role = "manifest_provenance"
    elif "history" in p or "ledger" in p: role = "history_ledger"
    elif "qa" in path.name or "checks" in path.name: role = "QA"
    elif suffix == ".png": role = "figure"
    elif "prediction" in path.name and "metric" not in path.name: role = "saved_predictions"
    elif "metric" in path.name or "comparison" in path.name: role = "metrics_comparison"
    elif "minute_2024" in path.name or "model_features" in p: role = "derived_dataset"
    elif p.startswith("data/"): role = "source_dataset"
    elif p.startswith("docs/"): role = "source_reference"
    elif suffix == ".py": role = "implementation"
    elif "requirements" in path.name: role = "environment"
    else: role = "supporting_evidence"
    retention = "retained_frozen_evidence"
    if "/reports/" in p or suffix == ".pdf" and not p.startswith("docs/"):
        retention = "historical_report_only_not_current_delivery"
    if suffix == ".pyc" or "__pycache__" in p: retention = "historical_cache"
    return version, role, retention


def main(refresh=False):
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "artifact_index.csv"
    if index_path.exists() and not refresh:
        raise FileExistsError("Index exists; do not replace frozen expectations")
    if not refresh:
        create_notebook()
        captions = []
        reviewed = {p: (key, scenario, cap) for key, p, scenario, cap in FIGURES}
        for p in sorted((ROOT / "outputs").rglob("*.png")):
            rel = p.relative_to(ROOT).as_posix()
            if rel in reviewed:
                key, scenario, caption = reviewed[rel]
                captions.append({"figure_id": key, "path": rel, "scenario": scenario, "status": "retained_with_authoritative_caption",
                                 "visual_reviewed": True, "must_show_caption": True, "raw_standalone_approved": False,
                                 "authoritative_caption": caption})
            else:
                captions.append({"figure_id": "ARCHIVE_" + p.stem, "path": rel, "scenario": "historical",
                                 "status": "historical_not_currently_approved", "visual_reviewed": False, "must_show_caption": False,
                                 "raw_standalone_approved": False, "authoritative_caption": "Historical figure; excluded from current retained set; no blanket caption approval."})
        pd.DataFrame(captions).to_csv(OUT / "figure_captions.csv", index=False)
        commands().to_csv(OUT / "commands.csv", index=False)
        scenarios = [
            ("A independent completed-minute sensors", "Original frozen restricted HGB plus V6 fixed extended Ridge/HGB history comparisons", "Historical training mean and nonnegative speed-cubic", "No new model selected. September positive mean (~232 kW) beats augmented Ridge (~564); October Ridge (~329) beats historical constants but retains negative R2.", "No current/past power predictor; all later evaluations inspected"),
            ("B conditional delayed labels", "Existing V7 daily residual Ridge and permitted October update", "Persistence and history mean with identical history/cutoff", "October residual Ridge ~120 kW beats matched baselines ~350/~329; September persistence ~956 beats calibration ~1147. Conditional reference only.", "Trustworthy labels, strict day-start minus 24h cutoff, daily refresh; unverified availability"),
            ("C original V7 simulated gaps", "Existing sealed-gap Ridge and residual correction", "Matched delayed persistence/history mean and fixed Ridge", "The 6h subset is strong but uses different anchors from other durations; at 24h history mean ~334 beats calibrated pooled ~414. No reliable transition repair.", "54 old gaps sealed across fits/history; independent predictors assumed available"),
            ("C paired V8 simulated gaps", "Unchanged V7-definition calibration; safeguards retained as failed evidence", "Matched delayed persistence and history mean", "Persistence broadly outperforms tested calibration at all paired horizons (~910/1021/1068 kW), yet still has severe transitions. No universal winner promoted.", "16 paired anchors and common 24h embargo; positive-only and zero-excluded scopes retrospective"),
            ("D same-package physics / package loss", "Exact synchronous torque/RPM audit only", "Instrument formula comparison; no independent ML ranking", "Useful consistency diagnostic; torque scale and outage validity unresolved. Entire-package loss/coordinated zero does not supply independent current-state evidence.", "Same-instrument data, unknown physical validity; no operational repair claim")]
        pd.DataFrame(scenarios, columns=["scenario", "retained_reference", "matched_baselines", "defensible_interpretation", "information_contract"]).to_csv(OUT / "scenario_comparisons.csv", index=False)
    if refresh:
        old = pd.read_csv(index_path)
        rows = old[old.retention.ne("readiness_implementation")].to_dict("records")
    else:
        rows = []
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file(): continue
            rel = p.relative_to(ROOT)
            text = rel.as_posix()
            if text.startswith((".git/", "outputs/task3_readiness/", "scripts/task3_readiness/", "notebooks/task3_frozen_evidence.ipynb")):
                continue
            version, role, retention = metadata(rel)
            rows.append({"path": text, "bytes": p.stat().st_size, "sha256": sha(p), "version": version,
                         "role": role, "retention": retention, "verification_command": "VERIFY",
                         "usage_note": "Frozen historical input; no mutation or refitting during readiness verification"})
    implementation = sorted((ROOT / "scripts/task3_readiness").glob("*.py")) + sorted((ROOT / "scripts/task3_readiness").glob("*.txt")) + [NOTEBOOK]
    for p in implementation:
        rows.append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p), "version": "readiness",
                     "role": "notebook" if p.suffix == ".ipynb" else "implementation", "retention": "readiness_implementation",
                     "verification_command": "NOTEBOOK" if p.suffix == ".ipynb" else "VERIFY", "usage_note": "Saved-output-only implementation; no model loading/training"})
    index = pd.DataFrame(rows)
    index.to_csv(index_path, index=False)
    models = index[index.role.eq("saved_model")].copy()
    models["estimator_loaded"] = False
    models["scenario"] = models.path.map(lambda p: "B updated history" if "updated_october" in p else "C sealed-gap experiment" if "/reconstruction/" in p or "v8/paired/" in p else "A fixed independent-sensor comparison")
    models["training_label_scope"] = models.path.map(lambda p: "observed broad labels" if "broad" in p else "historical positive/no raw-negative labels")
    models["training_provenance"] = models.path.map(lambda p: "outputs/task3_v8/paired/fit_inventory.csv" if "v8/paired" in p else "outputs/task3_v7/reconstruction/fit_inventory.csv" if "/reconstruction/" in p else "outputs/task3_v7/adaptation/update_fit_inventory.csv" if "updated_october" in p else "outputs/task3_v6/fit_inventory.csv" if "v6/models" in p else "outputs/task3/tables/frozen_selection.json")
    models.to_csv(OUT / "retained_model_registry.csv", index=False)
    pd.DataFrame([{"version": v, "persisted_estimators": False, "available_evidence": evidence,
                   "limitation": "Historical comparison weights were not persisted; no refit authorized or needed for saved-output verification"}
                  for v, evidence in [("V2", "metrics/manifests and limited calibration predictions"), ("V3", "metrics/manifests/features"), ("V4", "60 saved prediction vectors plus experiment metadata")]]).to_csv(OUT / "historical_model_storage_gaps.csv", index=False)
    print(f"Indexed {len(index)} files; {len(models)} saved model artifacts; historical hashes preserved on refresh", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-implementation-hashes", action="store_true", help="Update new readiness code hashes only; retain every historical expectation")
    args = parser.parse_args()
    main(args.refresh_implementation_hashes)
