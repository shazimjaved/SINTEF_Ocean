"""Independent timing, hidden-label, alignment and numerical V7 assertions."""
from __future__ import annotations

from common import *
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

CHECKS = []


def check(name: str, result: bool, evidence: str) -> None:
    CHECKS.append({"check_id": name, "status": "PASS" if result else "FAIL", "evidence": evidence})


def number_equal(a, b, atol=1e-6) -> bool:
    return bool((pd.isna(a) and pd.isna(b)) or np.isclose(a, b, rtol=1e-9, atol=atol))


def verify_metric(row, y, p) -> bool:
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    if len(y) != row.n or not len(y) or not np.isfinite(p).all():
        return False
    constant_y = np.ptp(y) <= 1e-12
    constant_p = np.ptp(p) <= 1e-10 * max(1., abs(float(np.mean(p))))
    expected = {"mae_kw": mean_absolute_error(y, p),
                "rmse_kw": np.sqrt(mean_squared_error(y, p)),
                "r2_score": r2_score(y, p) if len(y) > 1 else np.nan,
                "pearson_r": np.nan if constant_y or constant_p or len(y) < 2 else np.corrcoef(y, p)[0, 1],
                "bias_actual_minus_pred_kw": np.mean(y-p)}
    return all(number_equal(getattr(row, key), value) for key, value in expected.items())


def scope_mask(frame: pd.DataFrame, scope: str):
    good = frame.operational_eligible & frame.observed_truth
    return good if scope == "broader_forward" else good & frame[scope]


def verify_history(history: pd.DataFrame, ledger: pd.DataFrame, columns: list[str], fallback: float,
                   positive_only=False):
    h = history.loc[history.operational_eligible & history.observed_truth].copy()
    if positive_only:
        h = h[h.positive]
    h["time"] = pd.to_datetime(h.window_end_utc, utc=True)
    ok = True
    for r in ledger.itertuples():
        day = pd.Timestamp(r.prediction_day_utc)
        cutoff = day - pd.Timedelta(hours=24)
        pool = h[(h.time >= cutoff-pd.Timedelta(days=3)) & (h.time < cutoff)].sort_values("time")
        used = len(pool) >= 30
        ok &= (cutoff == pd.Timestamp(r.history_cutoff_exclusive_utc) and len(pool) == r.history_n
               and used == r.used_history)
        if len(pool):
            ok &= (pool.window_end_utc.iloc[-1] == r.last_history_ts
                   and pool.time.max() < cutoff)
            if "artificially_hidden" in pool:
                ok &= not pool.artificially_hidden.any()
        for c in columns:
            expected = float(np.median(pool.actual_kw-pool[c])) if used else 0.
            # tuple field names cannot preserve double underscores: use ledger lookup.
            saved = ledger.loc[ledger.prediction_day_utc.eq(r.prediction_day_utc), f"offset__{c}"].iloc[0]
            ok &= number_equal(expected, saved)
        expected_persist = float(pool.actual_kw.iloc[-1]) if used else fallback
        expected_mean = float(pool.actual_kw.mean()) if used else fallback
        ok &= number_equal(expected_persist, r.persistence_kw) and number_equal(expected_mean, r.history_mean_kw)
    return ok


def main() -> None:
    prepare()
    manifest = json.loads((OUT / "experiment_manifest.json").read_text())
    check("V7_PROTOCOL", manifest == protocol() and 12 not in MONTHS and 7 not in MONTHS and 11 not in MONTHS,
          "Frozen definitions, explicit 24h delay, development-only permitted months")
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from channel_config import COLUMN_TO_SOURCE
    check("V7_FEATURES", all(COLUMN_TO_SOURCE[c] == "onboard" for c in V2["B"])
          and all(not c.startswith("target") and "SHAFT_" not in c for c in COLS["B"]),
          "24 extended input columns are independent onboard measurements/counts; no shaft/Noon/provider inputs")
    a = pd.read_csv(OUT / "a_reused_v6_metrics.csv")
    v6 = pd.read_csv(ROOT / "outputs/task3_v6/development_metrics.csv")
    a_ok = len(a) == len(v6)
    precision = []
    for col in v6:
        if pd.api.types.is_numeric_dtype(v6[col]):
            delta = float((a[col]-v6[col]).abs().max())
            a_ok &= np.allclose(a[col], v6[col], rtol=0, atol=1e-10, equal_nan=True)
            precision.append({"artifact": "A reused metric", "field": col,
                              "max_decimal_read_difference": delta,
                              "canonical_dtype": str(v6[col].dtype)})
        else:
            a_ok &= a[col].equals(v6[col])
    check("V7_A_METRICS", a_ok,
          "72 V6 benchmark rows preserved numerically; CSV float64 reserialization tolerance 1e-10")
    p = pd.read_csv(OUT / "a_prediction_provenance.csv")
    check("V7_A_PROVENANCE", len(p) == 24 and all(digest(ROOT / r.source_prediction) == r.sha256 for r in p.itertuples()),
          "All 24 referenced V6 prediction hashes unchanged")

    source = {month: LOAD(month) for month in MONTHS}
    bframes = {month: pd.read_csv(OUT / f"adaptation/predictions_{name}.csv.gz", low_memory=False)
               for month, name in [(9, "september"), (10, "october")]}
    aligned = True
    eligibility_independent = True
    fixed_timing = True
    for month, pred in bframes.items():
        d = source[month]
        e = d.STW_kn.notna() & np.isfinite(d.STW_kn) & d.STW_kn.ge(3)
        seen = d.target_n.gt(0) & d[TARGET].notna()
        aligned &= pred.window_end_utc.equals(d.window_end_utc)
        aligned &= np.allclose(pred.actual_kw, d[TARGET], rtol=0, atol=1e-3, equal_nan=True)
        aligned &= np.array_equal(pred.observed_truth, seen) and np.array_equal(pred.operational_eligible, e)
        corrupted = d.copy()
        corrupted[TARGET] = np.nan
        corrupted.target_n = 0
        eligibility_independent &= np.array_equal(eligible(corrupted), pred.operational_eligible)
        for name in B_MODELS:
            fixed_timing &= (pd.to_datetime(pred[f"max_training_ts__{name}"], utc=True)
                             < pd.to_datetime(pred.window_end_utc, utc=True) - LAG).all()
    check("V7_B_ALIGN_ELIGIBILITY", aligned and eligibility_independent,
          "All B minute rows/source labels aligned; deleting current targets leaves eligibility unchanged")
    check("V7_B_FIXED_AVAILABILITY", fixed_timing
          and bframes[9]["fallback_old_model__B_hgb_broad_full"].sum() == 1440,
          "Fixed-model training labels precede each 24h cutoff; 1440 early September broad-model fallbacks explicit")
    fit = pd.read_csv(OUT / "adaptation/update_fit_inventory.csv")
    cutoff = pd.Timestamp("2024-09-30T00:00:00Z")
    full = pd.concat([source[m] for m in FIXED_MONTHS+[9]], ignore_index=True)
    update_ok = len(fit) == 3
    for r in fit.itertuples():
        d = full.loc[(ts(full) < cutoff) & eligible(full) & observed(full)]
        if DEFINITIONS[r.candidate]["labels"] != "broad":
            d = d[positive(d)]
        update_ok &= len(d) == r.train_n and d.window_end_utc.max() == r.last_label_ts
        update_ok &= pd.Timestamp(r.last_label_ts) < cutoff
    check("V7_B_UPDATE_CUTOFF", update_ok, "Three October refits independently reconstructed from permitted history strictly before Sep30")
    bh = pd.read_csv(OUT / "adaptation/fixed_history.csv.gz")
    ledger = pd.read_csv(OUT / "adaptation/daily_history_ledger.csv")
    pledger = pd.read_csv(OUT / "adaptation/daily_positive_history_ledger.csv")
    bs = json.loads((ROOT / "outputs/task3_v6/models/jan_jun_aug__baselines.json").read_text())
    cols = ["fixed__B_ridge_full", "fixed__B_hgb_full"]
    check("V7_B_HISTORY", verify_history(bh, ledger, cols, bs["training_mean_kw"])
          and verify_history(bh, pledger, [cols[0]], bs["training_mean_kw"], positive_only=True),
          "Every daily residual, persistence and history mean independently uses [day-4d,day-1d); no same-day/future labels")
    calibration_ok = True
    for month, pred in bframes.items():
        key = day_of(pred).map(lambda x: x.isoformat())
        lookup = ledger.set_index("prediction_day_utc")
        plookup = pledger.set_index("prediction_day_utc")
        calibration_ok &= np.allclose(pred.delayed_persistence, key.map(lookup.persistence_kw))
        calibration_ok &= np.allclose(pred.delayed_history_mean, key.map(lookup.history_mean_kw))
        for name in ["B_ridge_full", "B_hgb_full"]:
            calibration_ok &= np.allclose(pred[f"calibrated__{name}"],
                pred[f"fixed__{name}"] + key.map(lookup[f"offset__fixed__{name}"]))
        calibration_ok &= np.allclose(pred["calibrated_positive_history__B_ridge_full"],
            pred[cols[0]] + key.map(plookup[f"offset__{cols[0]}"]))
    check("V7_B_CALIBRATION_REPLAY", calibration_ok,
          "Saved assisted predictions exactly replay independent daily ledger values and matched-information baselines")

    blocks = pd.read_csv(OUT / "reconstruction_blocks.csv")
    starts = pd.to_datetime(blocks.start_utc, utc=True)
    ends = pd.to_datetime(blocks.end_utc, utc=True)
    check("V7_C_SCHEDULE", len(blocks) == 54 and blocks.block_id.is_unique
          and blocks.groupby("duration_hours").size().to_dict() == {1:18, 6:18, 24:18}
          and (starts.sort_values().iloc[1:].to_numpy() > ends.iloc[starts.argsort()].iloc[:-1].to_numpy()).all(),
          "54 predetermined disjoint calendar blocks; 18 each at 1h/6h/24h; zero value-based choices")
    global_hidden = {m: hidden_mask(d, blocks) for m, d in source.items()}
    visible = {m: seal_targets(d, global_hidden[m]) for m, d in source.items()}
    cfit = pd.read_csv(OUT / "reconstruction/fit_inventory.csv")
    train_ok = len(cfit) == 12
    baseline_ok = True
    for month, months in C_TRAIN.items():
        train = pd.concat([visible[m] for m in months], ignore_index=True)
        cutoff_c = pd.Timestamp(2024, month, 1, tz="UTC") - LAG
        for name in C_MODELS:
            chosen = training(train, name, cutoff_c)
            r = cfit[(cfit.evaluation_month == month) & (cfit.candidate == name)].iloc[0]
            train_ok &= len(chosen) == r.train_n and not chosen.artificially_hidden.any()
            train_ok &= chosen.window_end_utc.max() == r.last_label_ts and ts(chosen).max() < cutoff_c
        recalculated = baselines(train[ts(train) < cutoff_c])
        recorded = json.loads((OUT / f"reconstruction/baselines_m{month:02d}.json").read_text())
        baseline_ok &= all(number_equal(recorded[k], v) if isinstance(v, (float,int)) else recorded[k] == v
                           for k,v in recalculated.items())
    check("V7_C_GLOBAL_TRAIN_EXCLUSION", train_ok,
          "All 12 reconstruction fits independently exclude all scheduled gaps, including gaps in earlier training months")
    check("V7_C_BASELINE_EXCLUSION", baseline_ok,
          "All six mean/speed baseline fits recomputed with the same global gap mask and latency cutoff")
    all_c = []
    cal_ok = True
    hidden_ok = True
    dtype_ok = True
    cledger = pd.read_csv(OUT / "reconstruction/daily_history_ledger.csv")
    for month in C_TRAIN:
        h = pd.read_csv(OUT / f"reconstruction/visible_history_m{month:02d}.csv.gz")
        # Ridge.predict in the saved float32 pipeline returns float32. Pandas
        # CSV writes its shortest float32-roundtrippable decimals; restore that
        # storage type for an exact residual replay, instead of treating those
        # decimals as the full original binary64 prediction.
        original_decimal = h["fixed__B_ridge_full"].copy()
        h["fixed__B_ridge_full"] = h["fixed__B_ridge_full"].astype("float32")
        saved_pipeline = joblib.load(OUT / f"reconstruction/m{month:02d}__B_ridge_full.joblib")
        dtype_ok &= saved_pipeline.predict(source[month][COLS["B"]].iloc[:10].to_numpy(np.float32)).dtype == np.float32
        precision.append({"artifact": f"C history month {month}", "field": "fixed__B_ridge_full",
                          "max_decimal_read_difference": float((original_decimal-h["fixed__B_ridge_full"].astype(float)).abs().max()),
                          "canonical_dtype": "float32 verified from saved pipeline predict"})
        hide = global_hidden[month]
        hidden_ok &= h.loc[hide, "actual_kw"].isna().all() and not h.loc[hide, "observed_truth"].any()
        hidden_ok &= np.array_equal(h.artificially_hidden, hide)
        baseline = json.loads((OUT / f"reconstruction/baselines_m{month:02d}.json").read_text())
        l = cledger[cledger.evaluation_month == month]
        cal_ok &= verify_history(h, l, [f"fixed__{n}" for n in C_MODELS], baseline["mean_kw"])
        lookup = l.set_index("prediction_day_utc")
        for block in blocks[blocks.month == month].itertuples():
            pred = pd.read_csv(OUT / f"reconstruction/predictions_{block.block_id}.csv.gz")
            d = source[month]
            member = ts(d).gt(pd.Timestamp(block.start_utc)) & ts(d).le(pd.Timestamp(block.end_utc))
            real = d.loc[member]
            hidden_ok &= len(pred) == block.calendar_minutes and pred.window_end_utc.tolist() == real.window_end_utc.tolist()
            hidden_ok &= np.allclose(pred.actual_kw, real[TARGET], rtol=0, atol=1e-3, equal_nan=True)
            hidden_ok &= np.array_equal(pred.observed_truth, observed(real))
            hidden_ok &= np.array_equal(pred.operational_eligible, eligible(real))
            key = day_of(pred).map(lambda x: x.isoformat())
            for name in C_MODELS:
                fixed_values = pred[f"fixed__{name}"]
                if name == "B_ridge_full":
                    fixed_values = fixed_values.astype("float32")
                cal_ok &= np.allclose(pred[f"calibrated__{name}"], fixed_values+
                                      key.map(lookup[f"offset__fixed__{name}"]))
            cal_ok &= np.allclose(pred.delayed_persistence, key.map(lookup.persistence_kw))
            all_c.append(pred)
    check("V7_C_MASK_AND_TRUTH_ALIGNMENT", hidden_ok,
          "Every gap label sealed during fitting/history, then rejoined to its exact source minute; natural missing never replaced by zero")
    check("V7_C_HISTORY_REPLAY", cal_ok and dtype_ok,
          "All six histories/gap predictions replay exactly using verified Ridge float32 storage, strict lag and global hidden-label exclusion")
    c = pd.concat(all_c, ignore_index=True)
    cover = pd.read_csv(OUT / "reconstruction/block_coverage.csv")
    check("V7_C_COVERAGE", len(cover) == 54 and len(c) == 33480 and c.window_end_utc.is_unique
          and (cover.eligible_minutes == cover.scored_forward_n + cover.unscored_eligible_missing_n).all()
          and (cover.scored_forward_n == cover.positive_forward_n + cover.recorded_zero_forward_n
               + cover.negative_or_mixed_forward_n).all(),
          "All 33,480 calendar gap minutes retained; every missing/positive/zero/negative count reconciles")
    baseline_not_weakened = True
    for pred in [*bframes.values(), c]:
        scoreable = pred.operational_eligible & pred.observed_truth
        baseline_not_weakened &= not (scoreable & pred.history_n.between(1, 29)).any()
    check("V7_PERSISTENCE_COVERAGE", baseline_not_weakened,
          "No scored B/C prediction has only 1-29 history labels: the shared minimum-30 rule does not weaken reported persistence vs a one-label requirement")
    # Sentinel perturbation in earlier April gaps must leave May training and
    # predictions identical after sealing. This is an actual small Ridge refit.
    corrupted = source[4].copy()
    corrupted.loc[global_hidden[4], TARGET] = 987654321.
    corrupted.loc[global_hidden[4], "target_n"] = 4
    corrupt_visible = seal_targets(corrupted, global_hidden[4])
    replay_train = pd.concat([visible[1], visible[2], visible[3], corrupt_visible], ignore_index=True)
    chosen = training(replay_train, "B_ridge_full", pd.Timestamp("2024-04-30T00:00:00Z"))
    replay = FACTORY(DEFINITIONS["B_ridge_full"])
    replay.fit(chosen[COLS["B"]].to_numpy(np.float32), chosen[TARGET].to_numpy(np.float32))
    saved = joblib.load(OUT / "reconstruction/m05__B_ridge_full.joblib")
    x = source[5].loc[global_hidden[5], COLS["B"]].to_numpy(np.float32)
    check("V7_C_HIDDEN_SENTINEL_REPLAY", np.allclose(replay.predict(x), saved.predict(x), rtol=1e-8, atol=1e-5),
          "Replacing all April held-out target values with a huge sentinel leaves the refitted May Ridge gap predictions unchanged")

    bmetrics = pd.read_csv(OUT / "tables/b_adaptation_metrics.csv")
    bmetric_ok = True
    for r in bmetrics.itertuples():
        p = bframes[9 if r.period == "september" else 10]
        mask_row = scope_mask(p, r.scope)
        bmetric_ok &= verify_metric(r, p.loc[mask_row, "actual_kw"], p.loc[mask_row, r.method])
    check("V7_B_EXACT_METRICS", bmetric_ok, "Every B MAE/RMSE/sklearn R2/Pearson r/bias independently recomputed")
    cmetric_ok = True
    perblock = pd.read_csv(OUT / "tables/c_per_block_metrics.csv")
    groups = {k: p for k,p in c.groupby("block_id")}
    for r in perblock.itertuples():
        p = groups[r.block_id]
        m = scope_mask(p, r.scope)
        cmetric_ok &= verify_metric(r, p.loc[m, "actual_kw"], p.loc[m, r.method])
    pooled = pd.read_csv(OUT / "tables/c_pooled_duration_metrics.csv")
    for r in pooled.itertuples():
        p = c[c.duration_hours == r.duration_hours]
        m = scope_mask(p, r.scope)
        cmetric_ok &= verify_metric(r, p.loc[m, "actual_kw"], p.loc[m, r.method])
    check("V7_C_EXACT_METRICS", cmetric_ok,
          "Every scored block and pooled duration metric independently recomputed without dropping difficult rows")
    zero = pd.concat([bmetrics, pooled], ignore_index=True).query("scope=='recorded_zero'")
    check("V7_R2_PEARSON_DISTINCTION", zero.pearson_r.isna().all() and zero.constant_target.all()
          and zero.loc[zero.n.gt(1), "r2_score"].notna().all(),
          "Exact sklearn finite R2 convention on constant-zero labels retained and flagged; Pearson r stays undefined")
    # Daily B and C vectors include all observed eligible truths, not only n>=30
    # days. The >=30 rule affects the displayed stability summary only.
    daily = pd.read_csv(OUT / "tables/daily_metrics.csv")
    daily_ok = True
    for p in bframes.values():
        p["_date"] = day_of(p).dt.strftime("%Y-%m-%d")
    c["_date"] = day_of(c).dt.strftime("%Y-%m-%d")
    for r in daily.itertuples():
        if r.experiment == "B":
            p = bframes[9 if r.period == "september" else 10]
        else:
            p = c[c.duration_hours == r.duration_hours]
        m = scope_mask(p, r.scope) & p._date.eq(r.date)
        daily_ok &= len(p.loc[m]) == r.n and number_equal(mean_absolute_error(p.loc[m, "actual_kw"], p.loc[m, r.method]), r.mae_kw)
    check("V7_DAILY_RECOMPUTATION", daily_ok, "All saved daily sample counts and MAE reconstructed from timestamped predictions")
    csv_write(pd.DataFrame(precision), OUT / "numerical_precision_audit.csv")
    csv_write(pd.DataFrame(CHECKS), OUT / "v7_qa.csv")
    for r in CHECKS:
        print(r["status"], r["check_id"], r["evidence"])
    failed = sum(r["status"] == "FAIL" for r in CHECKS)
    print(f"{len(CHECKS)-failed} PASS; {failed} FAIL")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
