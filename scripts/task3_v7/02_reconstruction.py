"""C: deterministic missing blocks; globally sealed labels, delayed history."""
from __future__ import annotations

from common import *
import joblib
import time


def main() -> None:
    prepare()
    dest = OUT / "reconstruction"
    dest.mkdir(exist_ok=True)
    storage = dest / "prediction_storage.json"
    if not storage.exists():
        storage.write_text(json.dumps({"fixed__B_ridge_full": "float32 (saved pipeline output)",
            "fixed__B_hgb_broad_full": "float64", "calibrated_predictions": "float64",
            "actual_kw": "float64 representation of float32 compact source labels",
            "exact_history_replay": "Restore fixed__B_ridge_full to float32 when reading CSV; metric tables use saved decimal predictions"}, indent=2))
    if (dest / "completed.json").exists():
        print("PASS: existing V7 reconstruction preserved")
        return
    blocks = pd.read_csv(OUT / "reconstruction_blocks.csv")
    # truth is kept separately and joined only after every model/history output
    # for a month has been calculated. No target-derived input is generated.
    original = {month: LOAD(month) for month in MONTHS}
    hidden = {month: hidden_mask(frame, blocks) for month, frame in original.items()}
    visible = {month: seal_targets(frame, hidden[month]) for month, frame in original.items()}
    assert all(not observed(visible[m]).loc[hidden[m]].any() for m in MONTHS)
    fits = []
    block_rows = []
    ledgers = []
    for month, months_train in C_TRAIN.items():
        frame = visible[month]
        current = pd.Timestamp(2024, month, 1, tz="UTC")
        cutoff = current - LAG
        train = pd.concat([visible[m] for m in months_train], ignore_index=True)
        history = output_frame(frame)
        history["artificially_hidden"] = hidden[month]
        # Current-month target values inside every gap are already NaN here.
        assert not history.loc[history.artificially_hidden, "observed_truth"].any()
        baseline = baselines(train.loc[ts(train).lt(cutoff)])
        (dest / f"baselines_m{month:02d}.json").write_text(json.dumps(baseline, indent=2))
        for key, p in base_predict(frame, baseline).items():
            history[f"fixed_{key}"] = p
        for name in C_MODELS:
            selected = training(train, name, cutoff)
            assert not selected.artificially_hidden.any()
            assert ts(selected).max() < cutoff
            columns = COLS[DEFINITIONS[name]["group"]]
            pipeline = FACTORY(DEFINITIONS[name])
            started = time.perf_counter()
            pipeline.fit(selected[columns].to_numpy(np.float32), selected[TARGET].to_numpy(np.float32))
            elapsed = time.perf_counter() - started
            joblib.dump(pipeline, dest / f"m{month:02d}__{name}.joblib")
            history[f"fixed__{name}"] = pipeline.predict(frame[columns].to_numpy(np.float32))
            fits.append({"evaluation_month": month, "candidate": name,
                         "training_months": ",".join(str(x) for x in months_train),
                         "snapshot_utc": current.isoformat(), "label_cutoff_exclusive_utc": cutoff.isoformat(),
                         "train_n": len(selected), "last_label_ts": selected.window_end_utc.max(),
                         "first_label_ts": selected.window_end_utc.min(), "fit_seconds": elapsed,
                         "hidden_labels_in_fit": int(selected.artificially_hidden.sum())})
        # Calibrating only current-month out-of-time predictions avoids using
        # in-sample residuals from the model's earlier training months.
        columns = [f"fixed__{name}" for name in C_MODELS]
        offset, persistence, mean, ledger = daily_history(history, history, columns, baseline["mean_kw"])
        for col in columns:
            history[f"calibrated__{col.removeprefix('fixed__')}"] = history[col] + offset[col]
        history["delayed_persistence"] = persistence
        history["delayed_history_mean"] = mean
        ledger["evaluation_month"] = month
        ledgers.append(ledger)
        csv_write(history, dest / f"visible_history_m{month:02d}.csv.gz")
        lookup = ledger.set_index("prediction_day_utc")
        # Open the sealed truths only now, after fit, calibration and predictions.
        truth = output_frame(original[month])
        for block in blocks.loc[blocks.month.eq(month)].itertuples():
            start = pd.Timestamp(block.start_utc)
            end = pd.Timestamp(block.end_utc)
            member = ts(frame).gt(start) & ts(frame).le(end)
            result = truth.loc[member].copy()
            assert len(result) == block.calendar_minutes
            result["block_id"] = block.block_id
            result["duration_hours"] = block.duration_hours
            result["source_month"] = month
            for col in history:
                if col.startswith(("fixed_", "calibrated__", "delayed_")):
                    result[col] = history.loc[member, col].to_numpy()
            key = day_of(result).map(lambda x: x.isoformat())
            result["history_cutoff_exclusive_utc"] = key.map(lookup.history_cutoff_exclusive_utc)
            result["history_n"] = key.map(lookup.history_n)
            result["last_history_ts"] = key.map(lookup.last_history_ts)
            result["history_used"] = key.map(lookup.used_history)
            csv_write(result, dest / f"predictions_{block.block_id}.csv.gz")
            eligible_count = int(result.operational_eligible.sum())
            scored = result.operational_eligible & result.observed_truth
            block_rows.append({"block_id": block.block_id, "month": month,
                               "duration_hours": block.duration_hours,
                               "calendar_minutes": len(result), "eligible_minutes": eligible_count,
                               "observed_truth_minutes_all_speeds": int(result.observed_truth.sum()),
                               "natural_missing_minutes_all_speeds": int((~result.observed_truth).sum()),
                               "scored_forward_n": int(scored.sum()),
                               "unscored_eligible_missing_n": int((result.operational_eligible & ~result.observed_truth).sum()),
                               "positive_forward_n": int((scored & result.positive).sum()),
                               "recorded_zero_forward_n": int((scored & result.recorded_zero).sum()),
                               "negative_or_mixed_forward_n": int((scored & result.negative_or_mixed).sum()),
                               "status": "scored" if scored.any() else "unscorable; no observed forward truth"})
        print("C month", month, "fits complete; all nine calendar blocks retained", flush=True)
        csv_write(pd.DataFrame(fits), dest / "fit_inventory.csv")
        csv_write(pd.DataFrame(block_rows), dest / "block_coverage.csv")
    csv_write(pd.concat(ledgers, ignore_index=True), dest / "daily_history_ledger.csv")
    (dest / "completed.json").write_text(json.dumps({"completed": True, "blocks": len(block_rows),
        "global_hidden_minutes": int(sum(x.sum() for x in hidden.values())),
        "latency_hours": 24, "hidden_label_policy": "never revealed to subsequent C fits/history"}, indent=2))
    print("PASS: 54 disjoint blocked reconstruction cases saved; natural missing/zero states retained")


if __name__ == "__main__":
    main()
