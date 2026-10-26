"""Freeze quantile safeguards using Apr/May only; replay unchanged V7 models."""
from __future__ import annotations

from v8_common import *


def learn():
    path=OUT/"thresholds.json"
    if path.exists():return json.loads(path.read_text())
    scale_data=pd.concat([LOAD(m)[FEATURES] for m in [1,2,3]],ignore_index=True)
    scale={}
    for c in FEATURES:
        value=float(scale_data[c].quantile(.75)-scale_data[c].quantile(.25))
        scale[c]=value if value>0 else float(scale_data[c].std()) or 1.
    all_rows=[];all_days=[];provenance=[];errors=[]
    for month in [4,5]:
        h=load_v7_history(month)
        baseline=json.loads((OLD/f"reconstruction/baselines_m{month:02d}.json").read_text())
        frame,days=history_stats(h,h,baseline["mean_kw"])
        frame=reliability_features(frame,scale)
        all_rows.append(frame.loc[frame.operational_eligible&frame.history_used.astype(bool)])
        days["month"]=month;all_days.append(days[days.history_used])
        source=OLD/f"reconstruction/visible_history_m{month:02d}.csv.gz"
        provenance.append({"role":"legal historical residuals/onboard drift","month":month,
                           "path":str(source.relative_to(ROOT)),"sha256":DIGEST(source)})
        for p in sorted((OLD/"reconstruction").glob(f"predictions_m{month:02d}_*.csv.gz")):
            d=pd.read_csv(p)
            e=d.operational_eligible&d.observed_truth
            errors.extend((d.loc[e,"actual_kw"]-d.loc[e,"calibrated__B_ridge_full"]).abs().tolist())
            provenance.append({"role":"earlier validation error reference only","month":month,
                               "path":str(p.relative_to(ROOT)),"sha256":DIGEST(p)})
    rows=pd.concat(all_rows,ignore_index=True);days=pd.concat(all_days,ignore_index=True)
    limits={c:float(days[c].quantile(.99)) for c in
            ["zero_fraction","negative_fraction","cutoff_to_last_label_hours","residual_mad_kw"]}
    for c in ["onboard_history_drift","prediction_disagreement_kw"]:
        limits[c]=float(rows[c].quantile(.99))
    thresholds={"source_months":[4,5],"feature_scale_months":[1,2,3],"feature_iqr":scale,
                "offset_cap_kw":float(days.offset_kw.abs().quantile(.95)),
                "reference_error_kw":float(np.quantile(errors,.95)),"limits":limits,
                "history_days_used":len(days),"onboard_rows_used":len(rows),"reference_errors_n":len(errors),
                "quantile_levels_predeclared":protocol()["threshold_levels"],
                "interpretation":"risk flag and early-error reference, not current-state identification or validated probability"}
    path.write_text(json.dumps(thresholds,indent=2),encoding="utf-8")
    WRITE(days,OUT/"early_threshold_daily_history.csv")
    WRITE(pd.DataFrame(provenance),OUT/"threshold_provenance.csv")
    return thresholds


def main():
    prepare(); thresholds=learn()
    dest=OUT/"ablation";dest.mkdir(exist_ok=True)
    if (dest/"completed.json").exists():
        print("PASS: existing V8 V7-replay ablation preserved");return
    blocks=pd.read_csv(OLD/"reconstruction_blocks.csv")
    ledgers=[];sources=[]
    for month in [4,5,6,8,9,10]:
        history=load_v7_history(month)
        baseline=json.loads((OLD/f"reconstruction/baselines_m{month:02d}.json").read_text())
        d,days=history_stats(history,history,baseline["mean_kw"])
        d["training_mean"]=history.fixed_mean.to_numpy(float)
        d["speed_cubic"]=history.fixed_speed_cubic.to_numpy(float)
        d=apply_rules(d,thresholds)
        days["month"]=month;ledgers.append(days)
        pieces=[]
        for block in blocks[blocks.month.eq(month)].itertuples():
            original=OLD/f"reconstruction/predictions_{block.block_id}.csv.gz"
            truth=pd.read_csv(original)
            p=d[d.window_end_utc.isin(truth.window_end_utc)].copy()
            assert p.window_end_utc.tolist()==truth.window_end_utc.tolist()
            assert np.allclose(p.v7_calibrated,truth.calibrated__B_ridge_full,atol=1e-6)
            for c in ["actual_kw","observed_truth","positive","recorded_zero","negative_or_mixed"]:
                p[c]=truth[c].to_numpy()
            p["block_id"]=block.block_id;p["source_month"]=month
            p["duration_hours"]=block.duration_hours
            p["development_role"]="threshold_development" if month in [4,5] else "later_inspected_development"
            pieces.append(p)
            sources.append({"source_prediction":str(original.relative_to(ROOT)),"sha256":DIGEST(original)})
        WRITE(pd.concat(pieces,ignore_index=True),dest/f"v7_replay_m{month:02d}.csv.gz")
        print("V7 fixed-model robustness replay",month,flush=True)
    WRITE(pd.concat(ledgers,ignore_index=True),dest/"daily_information.csv")
    WRITE(pd.DataFrame(sources),dest/"v7_prediction_provenance.csv")
    (dest/"completed.json").write_text(json.dumps({"completed":True,"model_refits":0,
        "threshold_sha256":DIGEST(OUT/"thresholds.json")},indent=2))
    print("PASS: small frozen robustness ablation; V7 predictions and weights unchanged")


if __name__=="__main__":main()
