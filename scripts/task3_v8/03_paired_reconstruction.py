"""One fixed-definition Ridge per fold, new globally sealed paired gaps."""
from __future__ import annotations

from v8_common import *
import joblib
import time


def main():
    prepare()
    thresholds=json.loads((OUT/"thresholds.json").read_text())
    dest=OUT/"paired";dest.mkdir(exist_ok=True)
    if (dest/"completed.json").exists():
        print("PASS: existing V8 paired-gap experiment preserved");return
    new=pd.read_csv(OUT/"paired_anchors.csv")
    old=pd.read_csv(OLD/"reconstruction_blocks.csv")
    specification={"source_protocol_sha256":DIGEST(OUT/"experiment_manifest.json"),
                   "threshold_sha256":DIGEST(OUT/"thresholds.json"),
                   "old_mask_sha256":DIGEST(OLD/"reconstruction_blocks.csv"),
                   "global_mask":"union of all V7 gaps plus all V8 maximum-24h anchors",
                   "fit":"only Ridge alpha100, same V2 features/imputer/scaler; V7 model artifacts never modified",
                   "horizon_information":"identical prefix predictions from one sealed 24h union; no post-short-gap truth released"}
    (dest/"paired_protocol.json").write_text(json.dumps(specification,indent=2))
    source={m:LOAD(m) for m in MONTHS}
    hidden={m:V7["hidden_mask"](d,new)|V7["hidden_mask"](d,old) for m,d in source.items()}
    visible={m:V7["seal_targets"](d,hidden[m]) for m,d in source.items()}
    fits=[];ledgers=[];coverage=[]
    for month,months_train in FOLDS.items():
        train=pd.concat([visible[m] for m in months_train],ignore_index=True)
        cutoff=pd.Timestamp(2024,month,1,tz="UTC")-pd.Timedelta(hours=24)
        selected=TRAINING(train,"B_ridge_full",cutoff)
        assert not selected.artificially_hidden.any()
        pipeline=FACTORY(DEFINITION)
        start=time.perf_counter()
        pipeline.fit(selected[COLS["B"]].to_numpy(np.float32),selected[TARGET].to_numpy(np.float32))
        seconds=time.perf_counter()-start
        joblib.dump(pipeline,dest/f"ridge_m{month:02d}.joblib")
        baseline=V7["baselines"](train[TS(train).lt(cutoff)])
        (dest/f"baselines_m{month:02d}.json").write_text(json.dumps(baseline,indent=2))
        frame=visible[month]
        history=V7["output_frame"](frame)
        history["artificially_hidden"]=hidden[month]
        history["fixed_ridge"]=np.asarray(pipeline.predict(frame[COLS["B"]].to_numpy(np.float32)),dtype=np.float64)
        for c in FEATURES:history[c]=frame[c].to_numpy(float)
        predictions=V7["base_predict"](frame,baseline)
        history["training_mean"]=predictions["mean"]
        history["speed_cubic"]=predictions["speed_cubic"]
        d,ledger=history_stats(history,history,baseline["mean_kw"])
        d=apply_rules(d,thresholds)
        ledger["month"]=month;ledgers.append(ledger)
        WRITE(d,dest/f"sealed_history_m{month:02d}.csv.gz")
        fits.append({"month":month,"training_months":",".join(str(m) for m in months_train),
                     "label_cutoff_exclusive_utc":cutoff.isoformat(),"last_training_label_utc":selected.window_end_utc.max(),
                     "train_n":len(selected),"hidden_labels_in_fit":int(selected.artificially_hidden.sum()),
                     "fit_seconds":seconds,"definition_sha256":DIGEST(V7["V2_PATH"])})
        # Ground truth is joined only after all features, history summaries,
        # flags, corrections and predictions have been calculated.
        truth=V7["output_frame"](source[month])
        for anchor in new[new.month.eq(month)].itertuples():
            begin=pd.Timestamp(anchor.start_utc);end=pd.Timestamp(anchor.end_utc)
            member=TS(d).gt(begin)&TS(d).le(end)
            p=d.loc[member].copy()
            assert len(p)==1440
            for c in ["actual_kw","observed_truth","positive","recorded_zero","negative_or_mixed"]:
                p[c]=truth.loc[member,c].to_numpy()
            p["anchor_id"]=anchor.anchor_id;p["source_month"]=month
            p["elapsed_minutes"]=(TS(p)-begin).dt.total_seconds()/60
            e=p.operational_eligible&p.observed_truth
            p["truth_has_both_positive_zero"] = bool((e&p.positive).any() and (e&p.recorded_zero).any())
            WRITE(p,dest/f"predictions_{anchor.anchor_id}.csv.gz")
            for hours in [1,6,24]:
                q=p[p.elapsed_minutes.le(hours*60)]
                eligible=q.operational_eligible;observed=eligible&q.observed_truth
                coverage.append({"anchor_id":anchor.anchor_id,"month":month,"horizon_hours":hours,
                                 "calendar_n":len(q),"eligible_n":int(eligible.sum()),"scored_n":int(observed.sum()),
                                 "unscored_missing_n":int((eligible&~q.observed_truth).sum()),
                                 "positive_n":int((observed&q.positive).sum()),"zero_n":int((observed&q.recorded_zero).sum()),
                                 "negative_or_mixed_n":int((observed&q.negative_or_mixed).sum()),
                                 "anchor_truth_transition":bool(p.truth_has_both_positive_zero.iloc[0])})
        print("paired Ridge fold",month,len(selected),f"{seconds:.2f}s",flush=True)
    WRITE(pd.DataFrame(fits),dest/"fit_inventory.csv")
    WRITE(pd.concat(ledgers,ignore_index=True),dest/"daily_information.csv")
    cover=pd.DataFrame(coverage)
    matched=cover.groupby("anchor_id").scored_n.min().gt(0)
    complete=cover.groupby("anchor_id").unscored_missing_n.sum().eq(0)&matched
    cover["matched_any_truth"]=cover.anchor_id.map(matched)
    cover["matched_complete_eligible_truth"]=cover.anchor_id.map(complete)
    WRITE(cover,dest/"horizon_coverage.csv")
    (dest/"completed.json").write_text(json.dumps({"completed":True,"ridge_fits":4,
        "anchor_count":16,"horizon_count":48,"threshold_sha256":DIGEST(OUT/"thresholds.json")},indent=2))
    print("PASS: 16 globally embargoed anchors and identical-prefix 1h/6h/24h predictions saved")


if __name__=="__main__":main()
