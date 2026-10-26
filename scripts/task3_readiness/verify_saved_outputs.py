"""One CPU-only verification entrypoint for frozen Task 3 evidence.

Never import a training script, deserialize a model, generate predictions or
rewrite historical outputs. Only new readiness check files may be written.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import time

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "2"

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "outputs/task3_readiness"
TARGET = "SHAFT_MechPower_kW"
SOURCE_COLUMNS = ["window_end_utc", TARGET, "target_n", "target_min", "target_negative_n",
                  "STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
METRICS = ["n", "mae_kw", "rmse_kw", "r2_score", "pearson_r", "bias_actual_minus_pred_kw"]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path, **kwargs):
    return pd.read_csv(ROOT / path, **kwargs)


def moments(y, pred):
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    assert len(y) == len(pred) and np.isfinite(y).all() and np.isfinite(pred).all()
    n = len(y)
    if not n:
        return dict(n=0, **{key: np.nan for key in METRICS[1:]}, constant_target=False)
    error = y - pred
    constant = np.ptp(y) <= 1e-12
    constant_pred = np.ptp(pred) <= 1e-10 * max(1., abs(float(pred.mean())))
    sse = float(np.sum(error ** 2))
    denominator = float(np.sum((y - y.mean()) ** 2))
    r2 = np.nan if n < 2 else ((1. if sse == 0 else 0.) if constant else 1. - sse / denominator)
    return {"n": n, "mae_kw": float(np.abs(error).mean()), "rmse_kw": float(np.sqrt(np.mean(error ** 2))),
            "r2_score": r2, "pearson_r": np.nan if n < 2 or constant or constant_pred else float(np.corrcoef(y, pred)[0, 1]),
            "bias_actual_minus_pred_kw": float(error.mean()), "constant_target": bool(constant)}


def equal(a, b, atol=1e-7):
    return bool((pd.isna(a) and pd.isna(b)) or np.isclose(a, b, atol=atol, rtol=1e-9))


def assert_metrics(saved, current):
    for key in METRICS:
        if key not in saved:
            continue
        if key == "r2_score" and current["constant_target"]:
            # V6 stores undefined constant-target R2 as NaN; V7/V8 use sklearn's
            # finite convention. Neither representation establishes skill.
            assert pd.isna(saved[key]) or equal(saved[key], current[key]), (key, saved[key], current[key])
        else:
            assert equal(saved[key], current[key]), (key, saved[key], current[key])


class Verifier:
    def __init__(self, root=ROOT):
        assert Path(root).resolve() == ROOT
        self.checks = []
        self.sources = {}
        self.metric_rows = 0
        self.prediction_files = 0
        self.history_days = 0
        self.training_rows_checked = 0
        self.history_bounds = []

    def check(self, name, function):
        start = time.perf_counter()
        try:
            detail = function()
            status = "PASS"
        except Exception as error:
            status, detail = "FAIL", f"{type(error).__name__}: {error}"
        self.checks.append({"check_id": name, "status": status, "evidence": str(detail),
                            "elapsed_seconds": round(time.perf_counter() - start, 3)})
        print(f"{status}: {name}: {detail}", flush=True)

    def source(self, month):
        if month not in self.sources:
            d = read(f"outputs/task3/data/minute_2024_{month:02d}.csv.gz", usecols=SOURCE_COLUMNS,
                     dtype={c: "float32" for c in SOURCE_COLUMNS if c not in ["window_end_utc", "target_n", "target_negative_n"]})
            d = d.set_index("window_end_utc")
            assert d.index.is_unique and d.index.is_monotonic_increasing
            d["actual_kw"] = d[TARGET].astype(float)
            d["eligible"] = np.isfinite(d.STW_kn) & d.STW_kn.ge(3)
            d["observed"] = d.target_n.gt(0) & np.isfinite(d.actual_kw)
            assert d.target_n.eq(0).eq(~np.isfinite(d.actual_kw)).all()
            d["positive"] = d.observed & d.actual_kw.gt(0) & d.target_min.ge(0) & d.target_negative_n.eq(0)
            d["recorded_zero"] = d.observed & d.actual_kw.eq(0) & d.target_negative_n.eq(0)
            d["negative_or_mixed"] = d.observed & ~(d.positive | d.recorded_zero)
            d["active_zero"] = (d.eligible & d.recorded_zero & d.ME_RPM_CAMS.gt(50)
                                & d.ME_FuelLoad_pct.gt(20) & d.ME_ScavAirPressure_bar.gt(.5))
            assert (d.positive.astype(int) + d.recorded_zero.astype(int) + d.negative_or_mixed.astype(int)).eq(d.observed.astype(int)).all()
            self.sources[month] = d
        return self.sources[month]

    def hashes(self):
        index = read("outputs/task3_readiness/artifact_index.csv")
        historical = index[index.retention.ne("readiness_implementation")]
        assert len(historical) and historical.path.is_unique
        for row in index.itertuples():
            path = ROOT / row.path
            assert path.is_file(), row.path
            assert path.stat().st_size == row.bytes and sha256(path) == row.sha256, row.path
        return f"{len(historical)} historical artifacts plus {len(index)-len(historical)} implementation files match authoritative hashes; models hashed without loading"

    def policies(self):
        d = json.loads((ROOT / "outputs/task3_source_audit/audit_decision.json").read_text())
        assert d["decision"] == "C" and not d["source_issue_confirmed_in_this_release"]
        rules = read("outputs/task3_target_decision/audit_rules.csv").set_index("item").frozen_rule
        assert "STW>=3" in rules.eligibility and "independent" in rules.eligibility
        assert "quality uncertain" in rules.recorded_zero_scope
        assert "never scored" in rules.missing_truth
        source = read("outputs/task3_target_decision/source_zero_semantics.csv")
        assert not source.definitive_zero_sentinel_specification_found.any()
        for month in [1, 2, 3, 4, 5, 6, 8, 9, 10]:
            self.source(month)
        return "Zero remains observed and quality-uncertain; missing truth stays absent; positive and zero-excluded scopes are retrospective"

    def features_and_manifests(self):
        tree = ast.parse((ROOT / "scripts/channel_config.py").read_text(encoding="utf-8"))
        mapping = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "CHANNELS" for t in n.targets))
        sources = {v[0]: v[1] for v in mapping.values()}
        m = json.loads((ROOT / "outputs/task3_v7/experiment_manifest.json").read_text())
        assert len(m["features"]["B"]) == 24 and len(m["features"]["A"]) == 16
        for group in m["features"].values():
            for col in group:
                base = col.split("__", 1)[-1]
                assert sources[base] == "onboard" and "SHAFT_" not in col and not col.startswith("target")
        for filename, key, codepath in [
            ("outputs/task3_v6/experiment_manifest.json", "candidate_source_sha256", "scripts/task3_v2/07_walkforward_experiments.py"),
            ("outputs/task3_v7/experiment_manifest.json", "source_V2_sha256", "scripts/task3_v2/07_walkforward_experiments.py"),
            ("outputs/task3_v8/experiment_manifest.json", "source_v7_common_sha256", "scripts/task3_v7/common.py")]:
            spec = json.loads((ROOT / filename).read_text())
            assert spec[key] == sha256(ROOT / codepath), filename
        return "Frozen feature allowlists and definition hashes agree; no historical module or model executed"

    def align(self, p, month):
        assert p.window_end_utc.is_unique
        p = p.set_index("window_end_utc")
        s = self.source(month).loc[p.index]
        assert np.allclose(p.actual_kw, s.actual_kw, rtol=0, atol=1e-8, equal_nan=True)
        for flag, sourceflag in [("positive", "positive"), ("headline", "positive"), ("recorded_zero", "recorded_zero"),
                                 ("negative_or_mixed", "negative_or_mixed"), ("operational_eligible", "eligible"),
                                 ("observed_truth", "observed")]:
            if flag in p:
                assert np.array_equal(p[flag], s[sourceflag]), (month, flag)
        self.prediction_files += 1
        return p

    def check_target_comparisons(self):
        expected = read("outputs/task3_target_decision/scope_metrics.csv")
        assert len(expected) == 912
        gap_parts, paired_parts = [], []
        for path in sorted((ROOT / "outputs/task3_v7/reconstruction").glob("predictions_m*.csv.gz")):
            p = pd.read_csv(path, low_memory=False)
            p = self.align(p, int(p.source_month.iloc[0])); gap_parts.append(p)
        for path in sorted((ROOT / "outputs/task3_v8/paired").glob("predictions_m*.csv.gz")):
            p = pd.read_csv(path, low_memory=False)
            p = self.align(p, int(p.source_month.iloc[0])); paired_parts.append(p)
        gaps, paired = pd.concat(gap_parts), pd.concat(paired_parts)
        assert gaps.index.is_unique and paired.index.is_unique
        full_sources = pd.concat([self.source(m) for m in [1, 2, 3, 4, 5, 6, 8, 9, 10]])
        keys = ["experiment", "period", "training_history", "horizon_hours"]
        for (experiment, period, training, horizon), rows in expected.groupby(keys, sort=False):
            if experiment == "V6_fixed":
                month = int(period[-2:]); s = self.source(month)
                p = pd.DataFrame(index=s.index)
                for method in rows.method.unique():
                    word = {9: "september", 10: "october"}[month]
                    path = f"outputs/task3_v6/predictions/{training}__{method}__{word}.csv.gz"
                    raw = self.align(read(path), month)
                    p[method] = raw.predicted_kw
            elif experiment == "V7_adaptation":
                month = int(period[-2:]); s = self.source(month)
                word = {9: "september", 10: "october"}[month]
                p = self.align(read(f"outputs/task3_v7/adaptation/predictions_{word}.csv.gz", low_memory=False), month)
            else:
                p = gaps if experiment == "V7_reconstruction" else paired
                if period != "all_sampled_months":
                    p = p[p.source_month.eq(int(period[-2:]))]
                if horizon:
                    p = p[p.duration_hours.eq(horizon)] if experiment == "V7_reconstruction" else p[p.elapsed_minutes.le(horizon * 60)]
                s = full_sources.loc[p.index]
            assert p.index.equals(s.index)
            eligible, observed = s.eligible, s.observed
            broad = eligible & observed
            assert int(broad.sum()) == int(rows.observed_eligible_n.iloc[0])
            assert int(eligible.sum()) == int(rows.eligible_n.iloc[0])
            assert int((eligible & ~observed).sum()) == int(rows.missing_truth_eligible_n.iloc[0])
            masks = {"broader_forward": broad, "positive_only": broad & s.positive,
                     "broader_without_recorded_zeros": broad & ~s.recorded_zero,
                     "broader_without_active_engine_zeros": broad & ~s.active_zero,
                     "recorded_zero": broad & s.recorded_zero, "negative_or_mixed": broad & s.negative_or_mixed}
            for method, group in rows.groupby("method", sort=False):
                assert np.isfinite(p.loc[broad, method]).all(), (experiment, period, method)
                for row in group.to_dict("records"):
                    mask = masks[row["scope"]]
                    assert_metrics(row, moments(s.loc[mask, "actual_kw"], p.loc[mask, method]))
                    assert int((eligible & np.isfinite(p[method])).sum()) == row["predicted_eligible_n"]
                    assert equal(mask.sum() / eligible.sum() if eligible.sum() else np.nan, row["scored_scope_coverage_of_eligible"])
                    self.metric_rows += 1
        self.gaps, self.paired = gaps, paired
        return f"{self.metric_rows} frozen scope rows recomputed from saved vectors, with target-independent denominators and missing-truth coverage"

    def legacy_metrics(self):
        count = 0
        # V4 retains predictions for all its historical comparisons, but no
        # serialized model weights. Verification does not recreate those fits.
        table = read("outputs/task3_v4/models/v4_boosting_development.csv")
        for (fold, candidate), rows in table.groupby(["fold", "candidate"], sort=False):
            month = int(rows.validation_month.iloc[0])
            p = self.align(read(f"outputs/task3_v4/models/predictions/{fold}__{candidate}.csv.gz"), month)
            for row in rows.to_dict("records"):
                mask = p.headline if row["scope"] == "headline" else pd.Series(True, index=p.index)
                saved = {**row, "bias_actual_minus_pred_kw": row["bias_kw"]}
                assert_metrics(saved, moments(p.loc[mask, "actual_kw"], p.loc[mask, "predicted_kw"])); count += 1
        # V1 stress and original December evaluation: numeric replay only.
        # December is never an input to selection or to scenario preferences.
        stress = read("outputs/task3/tables/stress_predictions_metric_audit.csv.gz")
        test = read("outputs/task3/tables/test_predictions.csv.gz").rename(columns={
            TARGET: "actual_kw", "prediction_kw": "selected_model", "mean_baseline_kw": "training_mean", "speed_cube_kw": "speed_cubic"})
        for p, path in [(stress, "outputs/task3/tables/stress_metrics.csv"), (test, "outputs/task3/tables/test_metrics.csv")]:
            assert p.window_end_utc.is_unique
            for row in read(path).to_dict("records"):
                mask = p.headline if row["scope"] == "headline" else pd.Series(True, index=p.index)
                assert_metrics(row, moments(p.loc[mask, "actual_kw"], p.loc[mask, row["model"]])); count += 1
        return f"{count} V4/V1 archived metric rows reproduced; original December replay is historical verification only"

    def error_partition(self):
        parts = read("outputs/task3_target_decision/observed_error_partition.csv")
        metrics = read("outputs/task3_target_decision/scope_metrics.csv")
        keys = ["experiment", "period", "training_history", "horizon_hours", "selection", "method"]
        broad = metrics[metrics.scope.eq("broader_forward")].set_index(keys)
        for key, group in parts.groupby(keys, dropna=False):
            row = broad.loc[key]
            assert group.n.sum() == row.n
            assert set(group.component) == {"positive", "recorded_zero", "negative_or_mixed"}
            for column in ["sum_absolute_error_kw", "sum_squared_error_kw2"]:
                assert equal(group[column].sum(), row[column], atol=1e-5)
        assert self.gaps.block_id.nunique() == 54 and self.paired.anchor_id.nunique() == 16
        return "Every observed error partition reconciles; all 54 old blocks and 16 paired anchors retained; no causal validity claim"

    @staticmethod
    def hidden(index, schedules):
        times = pd.to_datetime(index, utc=True)
        mask = np.zeros(len(index), bool)
        for row in schedules.itertuples():
            mask |= (times > pd.Timestamp(row.start_utc)) & (times <= pd.Timestamp(row.end_utc))
        return mask

    def training_availability(self):
        inv = read("outputs/task3_v6/fit_inventory.csv")
        histories = {"jan_jun": [1, 2, 3, 4, 5, 6], "jan_jun_aug": [1, 2, 3, 4, 5, 6, 8]}
        for row in inv.itertuples():
            d = pd.concat([self.source(m) for m in histories[row.training_arm]])
            use = d.eligible & d.observed
            if row.training_labels != "broad": use &= d.positive
            chosen = d[use]
            assert len(chosen) == row.train_n and chosen.index.min() == row.first_training_timestamp and chosen.index.max() == row.last_training_timestamp
            assert pd.Timestamp(row.last_training_timestamp) < pd.Timestamp("2024-09-01T00:01Z")
            self.training_rows_checked += len(chosen)
        old = read("outputs/task3_v7/reconstruction_blocks.csv")
        anchors = read("outputs/task3_v8/paired_anchors.csv")
        assert {"start_utc", "end_utc"}.issubset(anchors.columns)
        for version, inventory, schedules in [
            (7, "outputs/task3_v7/reconstruction/fit_inventory.csv", old),
            (8, "outputs/task3_v8/paired/fit_inventory.csv", pd.concat([old, anchors], ignore_index=True))]:
            for row in read(inventory).itertuples():
                months = [int(v) for v in row.training_months.split(",")]
                assert set(months).isdisjoint({7, 11, 12})
                d = pd.concat([self.source(m) for m in months])
                cutoff = pd.Timestamp(row.label_cutoff_exclusive_utc)
                use = d.eligible & d.observed & (pd.to_datetime(d.index, utc=True) < cutoff) & ~self.hidden(d.index, schedules)
                if version == 8 or row.candidate == "B_ridge_full": use &= d.positive
                chosen = d[use]
                last = row.last_training_label_utc if version == 8 else row.last_label_ts
                assert len(chosen) == row.train_n and chosen.index.max() == last and pd.Timestamp(last) < cutoff
                assert row.hidden_labels_in_fit == 0
                self.training_rows_checked += len(chosen)
        update = read("outputs/task3_v7/adaptation/update_fit_inventory.csv")
        d = pd.concat([self.source(m) for m in [1, 2, 3, 4, 5, 6, 8, 9]])
        for row in update.itertuples():
            use = d.eligible & d.observed & (pd.to_datetime(d.index, utc=True) < pd.Timestamp(row.label_cutoff_exclusive_utc))
            if row.candidate != "B_hgb_broad_full": use &= d.positive
            assert int(use.sum()) == row.train_n
            assert pd.Timestamp(row.last_label_ts) < pd.Timestamp(row.label_cutoff_exclusive_utc)
            assert pd.Timestamp(row.snapshot_utc) - pd.Timestamp(row.label_cutoff_exclusive_utc) == pd.Timedelta(hours=24)
        for month, word in [(9, "september"), (10, "october")]:
            p = read(f"outputs/task3_v7/adaptation/predictions_{word}.csv.gz", low_memory=False)
            t = pd.to_datetime(p.window_end_utc, utc=True)
            for c in p.columns[p.columns.str.startswith("max_training_ts__")]:
                assert (pd.to_datetime(p[c], utc=True) < t - pd.Timedelta(hours=24)).all(), c
        return "V6 counts/chronology, V7 updates and strict 24h model fallback, V7/V8 sealed-gap train counts/cutoffs reconstructed without fitting"

    def ledger(self, history, records, version, positive_only=False):
        h = history[history.operational_eligible & history.observed_truth].copy()
        if positive_only: h = h[h.positive]
        h["_time"] = pd.to_datetime(h.window_end_utc, utc=True)
        for record in records.to_dict("records"):
            day = pd.Timestamp(record["prediction_day_utc"])
            cutoff = day - pd.Timedelta(hours=24)
            assert cutoff == pd.Timestamp(record["history_cutoff_exclusive_utc"])
            pool = h[h._time.ge(cutoff - pd.Timedelta(days=3)) & h._time.lt(cutoff)].sort_values("_time")
            n = len(pool); used = n >= 30
            assert n == record["history_n"]
            assert used == record["used_history" if version == 7 else "history_used"]
            if n:
                lastcol = "last_history_ts" if version == 7 else "last_admitted_label_utc"
                assert pd.Timestamp(record[lastcol]) == pool._time.max() < cutoff
                if "artificially_hidden" in pool: assert not pool.artificially_hidden.any()
            if version == 7:
                for col in [c for c in records.columns if c.startswith("offset__")]:
                    base = col.removeprefix("offset__")
                    expected = float((pool.actual_kw - pool[base]).median()) if used else 0.
                    assert equal(expected, record[col]), (day, col)
            else:
                expected = float((pool.actual_kw - pool.fixed_ridge).median()) if used else 0.
                assert equal(expected, record["offset_kw"])
                if n:
                    for flag, key in [("recorded_zero", "zero_fraction"), ("positive", "positive_fraction"), ("negative_or_mixed", "negative_fraction")]:
                        assert equal(pool[flag].mean(), record[key])
            if used:
                assert equal(pool.actual_kw.iloc[-1], record["persistence_kw"])
                assert equal(pool.actual_kw.mean(), record["history_mean_kw"])
            self.history_days += 1
            self.history_bounds.append({"prediction_day_utc": day.isoformat(), "cutoff_exclusive_utc": cutoff.isoformat(),
                                        "history_n": n, "latest_admitted_utc": pool._time.max().isoformat() if n else "",
                                        "positive_history_only": positive_only, "version": version})

    def delayed_history(self):
        h = read("outputs/task3_v7/adaptation/fixed_history.csv.gz", low_memory=False)
        self.ledger(h, read("outputs/task3_v7/adaptation/daily_history_ledger.csv"), 7)
        self.ledger(h, read("outputs/task3_v7/adaptation/daily_positive_history_ledger.csv"), 7, True)
        old_blocks = read("outputs/task3_v7/reconstruction_blocks.csv")
        both = pd.concat([old_blocks, read("outputs/task3_v8/paired_anchors.csv")], ignore_index=True)
        old_records = read("outputs/task3_v7/reconstruction/daily_history_ledger.csv")
        new_records = read("outputs/task3_v8/paired/daily_information.csv")
        for month in [4, 5, 6, 8, 9, 10]:
            h = read(f"outputs/task3_v7/reconstruction/visible_history_m{month:02d}.csv.gz", dtype={"fixed__B_ridge_full": "float32"})
            hidden = self.hidden(h.window_end_utc, old_blocks)
            assert np.array_equal(hidden, h.artificially_hidden)
            assert h.loc[hidden, "actual_kw"].isna().all() and not h.loc[hidden, "observed_truth"].any()
            self.ledger(h, old_records[old_records.evaluation_month.eq(month)], 7)
        for month in [6, 8, 9, 10]:
            h = read(f"outputs/task3_v8/paired/sealed_history_m{month:02d}.csv.gz", dtype={"fixed_ridge": "float32"}, low_memory=False)
            hidden = self.hidden(h.window_end_utc, both)
            assert np.array_equal(hidden, h.artificially_hidden)
            assert h.loc[hidden, "actual_kw"].isna().all() and not h.loc[hidden, "observed_truth"].any()
            self.ledger(h, new_records[new_records.month.eq(month)], 8)
        return f"{self.history_days} daily ledgers replayed: strict earlier-only cutoffs, residuals, matched baselines and global hidden-label exclusion"

    def horizons_and_thresholds(self):
        coverage = read("outputs/task3_v8/paired/horizon_coverage.csv")
        for row in coverage.itertuples():
            p = self.paired[self.paired.anchor_id.eq(row.anchor_id) & self.paired.elapsed_minutes.le(row.horizon_hours * 60)]
            e = p.operational_eligible; obs = e & p.observed_truth
            for actual, expected in [(len(p), row.calendar_n), (e.sum(), row.eligible_n), (obs.sum(), row.scored_n),
                                     ((e & ~p.observed_truth).sum(), row.unscored_missing_n),
                                     ((obs & p.positive).sum(), row.positive_n), ((obs & p.recorded_zero).sum(), row.zero_n)]:
                assert actual == expected
        thresholds = json.loads((ROOT / "outputs/task3_v8/thresholds.json").read_text())
        assert thresholds["source_months"] == [4, 5] and thresholds["feature_scale_months"] == [1, 2, 3]
        prov = read("outputs/task3_v8/threshold_provenance.csv")
        assert set(prov.month) == {4, 5}
        assert all(sha256(ROOT / r.path) == r.sha256 for r in prov.itertuples())
        accepted_zero = self.paired.operational_eligible & self.paired.observed_truth & self.paired.recorded_zero & ~self.paired.abstain
        assert accepted_zero.sum() == 2160
        assert equal(moments(self.paired.loc[accepted_zero, "actual_kw"], self.paired.loc[accepted_zero, "v7_calibrated"])["mae_kw"], 4434.843862462927)
        return "All paired horizon denominators and naturally missing truths reconcile; early-only threshold provenance retained; dangerous accepted-zero errors preserved"

    def figure_and_notebook_contract(self):
        figures = read("outputs/task3_readiness/figure_captions.csv")
        retained = figures[figures.status.eq("retained_with_authoritative_caption")]
        assert len(retained) == 12 and retained.visual_reviewed.all()
        assert retained.authoritative_caption.str.contains("retrospective", case=False).all()
        for row in retained.itertuples():
            assert (ROOT / row.path).is_file() and row.must_show_caption
        import nbformat
        nb = nbformat.read(ROOT / "notebooks/task3_frozen_evidence.ipynb", as_version=4)
        nbformat.validate(nb)
        assert any("run_verification" in cell.source for cell in nb.cells if cell.cell_type == "code")
        assert not any(cell.source.lstrip().startswith(("!", "%")) for cell in nb.cells if cell.cell_type == "code")
        return "12 visually reviewed retained figures have mandatory retrospective captions; actual notebook validates and calls the single verifier"

    def fault_checks(self):
        healthy = moments([1., 2., 3.], [3., 4., 5.])
        assert equal(healthy["r2_score"], -5.) and equal(healthy["pearson_r"], 1.)
        try:
            assert_metrics({**healthy, "mae_kw": healthy["mae_kw"] + 1.}, healthy)
        except AssertionError:
            pass
        else:
            raise AssertionError("Corrupted metric was not rejected")
        assert moments([], [])["n"] == 0 and pd.isna(moments([], [])["mae_kw"])
        assert moments([0., 0.], [1., 1.])["constant_target"]
        schedule = pd.DataFrame({"start_utc": ["2024-06-01T00:00Z"], "end_utc": ["2024-06-01T01:00Z"]})
        assert self.hidden(["2024-06-01T00:00Z", "2024-06-01T00:01Z", "2024-06-01T01:00Z", "2024-06-01T01:01Z"], schedule).tolist() == [False, True, True, False]
        return "Independent known-value metrics, corrupted-MAE rejection, empty/constant truth and exact embargo boundaries verified in memory"


def run_verification(output_dir=None):
    verifier = Verifier()
    stages = [("FROZEN_HASHES", verifier.hashes), ("TARGET_POLICY", verifier.policies),
              ("FEATURES_MANIFESTS", verifier.features_and_manifests), ("SCOPE_METRICS_COVERAGE", verifier.check_target_comparisons),
              ("LEGACY_METRICS", verifier.legacy_metrics), ("ERROR_PARTITION", verifier.error_partition),
              ("TRAIN_CHRONOLOGY", verifier.training_availability), ("DELAYED_HISTORY", verifier.delayed_history),
              ("HORIZONS_THRESHOLDS", verifier.horizons_and_thresholds), ("FIGURE_NOTEBOOK_CONTRACT", verifier.figure_and_notebook_contract),
              ("VERIFIER_FAULT_CHECKS", verifier.fault_checks)]
    for name, function in stages:
        verifier.check(name, function)
    frame = pd.DataFrame(verifier.checks)
    if output_dir is not None:
        output = Path(output_dir).resolve()
        assert output.is_relative_to(READINESS.resolve()), "Write only under the readiness directory"
        output.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output / "verification_checks.csv", index=False)
        pd.DataFrame(verifier.history_bounds).to_csv(output / "verified_history_bounds.csv", index=False)
    return frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=READINESS / "verification")
    args = parser.parse_args()
    result = run_verification(args.output_dir)
    raise SystemExit(0 if result.status.eq("PASS").all() else 1)
