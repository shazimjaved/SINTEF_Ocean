"""Executable V2 diagnostic and development-experiment QA gate."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error,r2_score

ROOT=Path("outputs/task3_v2")
P1=ROOT/"phase1"
EX=ROOT/"experiments"
DATA=ROOT/"data"
ROWS=[]


def check(claim,okay,evidence):
    ROWS.append({"id":f"V2Q{len(ROWS)+1:02d}","claim":claim,
                 "status":"PASS" if okay else "FAIL","evidence":str(evidence)})


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda:file.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def main():
    old=json.loads(Path("outputs/task3/tables/frozen_artifact_sha256.json").read_text(encoding="utf-8"))
    check("V1 model, frozen selection, original December predictions and metrics remain unchanged",
          all(digest(path)==value for path,value in old.items()),f"hashes={len(old)}")
    trace=pd.read_csv(P1/"raw_minute_trace.csv")
    zero_trace=pd.read_csv(P1/"zero_power_raw_trace.csv")
    check("Registered target QID/unit and sampled raw-to-minute target/engine means reconcile",
          len(trace)==20 and trace["pass"].all()
          and trace.loc[trace.column=="SHAFT_MechPower_kW","unit"].str.lower().eq("kw").all(),
          "20/20 representative records across January, August, October, December")
    check("Three long zero-power runs contain raw zero target readings with matching active-engine sensors",
          len(zero_trace)==15 and zero_trace["pass"].all()
          and zero_trace.loc[zero_trace.column=="SHAFT_MechPower_kW","raw_max"].eq(0).all(),
          "15/15 raw channel-minute checks across three runs")
    run=pd.read_csv(P1/"zero_power_runs_yearwide.csv")
    check("Long zero-power plateaus are reconciled across month boundaries",
          int(run.minutes.max())==11773
          and ((run.minutes==9603)&run.start_utc.str.startswith("2024-08")).any(),
          f"top run minutes={run.minutes.head(3).tolist()}")
    zero=pd.read_csv(P1/"zero_power_monthly.csv")
    flags=pd.read_csv(DATA/"minute_label_quality_2024.csv.gz")
    flag_summary=pd.read_csv(DATA/"label_quality_monthly.csv")
    check("V2 quality flags cover the full year and reproduce zero-power month counts",
          len(flags)==527040 and flags.window_end_utc.is_unique
          and flag_summary.zero_forward.to_list()==zero.zero_forward_minutes.to_list()
          and int(flags.zero_forward_active_engine.sum())==38990,
          f"minutes={len(flags)}; active-engine zero={int(flags.zero_forward_active_engine.sum())}")
    monthly=pd.read_csv(P1/"monthly_distributions.csv")
    check("Target-conditional headline counts remain unchanged in V2 annotations",
          flag_summary.headline_minutes.to_list()==monthly.headline_minutes.to_list()
          and flags.headline_eligible.sum()==monthly.headline_minutes.sum(),
          "All twelve monthly headline counts reconcile")
    manifest=json.loads((DATA/"quality_flag_manifest.json").read_text(encoding="utf-8"))
    check("Target-derived quality flags are explicitly excluded from model input",
          "none" in manifest["model_input_status"]
          and set(flags.columns).isdisjoint({"prediction_kw","pred_raw"}),
          manifest["model_input_status"])
    cells=pd.read_csv(P1/"conditional_shift_summary.csv")
    neighbors=pd.read_csv(P1/"nearest_neighbor_shift.csv")
    check("Conditional comparison and nearest-neighbor shift tables have matched support counts",
          len(cells)==6 and (cells.common_cells_n>0).all()
          and len(neighbors)==16 and neighbors.matched_n.le(neighbors.complete_case_n).all(),
          f"cell rows={len(cells)}; neighbor rows={len(neighbors)}")
    relation=pd.read_csv(P1/"sensor_relationship_transfer.csv")
    check("Target and non-target sensor relationship shifts are separately recorded",
          relation.response.nunique()>1
          and ((relation.response=="ME_ScavAirPressure_bar")
               &(relation.predictor=="ME_FuelLoad_pct")).any(),
          f"relationships={len(relation)}")
    v2=json.loads((EX/"v2_experiment_manifest.json").read_text(encoding="utf-8"))
    folds=v2["folds"]
    months={m for _,training,val in folds for m in training+[val]}
    check("Walk-forward development folds are chronological and exclude July, November and December",
          len(folds)==4 and months.isdisjoint({7,11,12})
          and all(max(training)<val for _,training,val in folds),
          folds)
    result=pd.read_csv(EX/"v2_walkforward_results.csv")
    check("Every declared V2 candidate ran on every fold and both unchanged evaluation scopes",
          len(result)==len(folds)*len(v2["candidates"])*2
          and result.groupby(["fold","candidate"]).scope.nunique().eq(2).all()
          and result.n.gt(0).all() and np.isfinite(result.mae_kw).all(),
          f"rows={len(result)}; candidates={len(v2['candidates'])}")
    expected={"apr":42465,"may":17851,"jun":12084,"aug":35086}
    check("V2 fold headline counts reconcile with prior monthly audit",
          all(result.loc[(result.fold==fold)&(result.scope=="headline"),"n"].eq(n).all()
                  for fold,n in expected.items()),expected)
    weather=pd.read_csv(EX/"v2_weather_development.csv")
    check("Exploratory weather comparison uses only the same four development folds",
          len(weather)==24 and set(weather.fold)==set(expected)
          and weather.groupby(["fold","candidate"]).scope.nunique().eq(2).all(),
          f"rows={len(weather)}")
    bias=pd.read_csv(EX/"v2_bias_decomposition.csv")
    check("Bias decomposition satisfies MSE = squared bias + residual variance",
          len(bias)==36
          and np.allclose(bias.mse_kw2,bias.squared_bias_kw2+bias.residual_variance_kw2,
                          rtol=1e-10,atol=1e-5)
          and (bias.bias_pct_mse.between(0,100)).all(),
          f"rows={len(bias)}")
    calibration=pd.read_csv(EX/"offline_calibration_upper_bound.csv")
    saved=pd.read_csv(EX/"offline_calibration_predictions.csv.gz")
    okay=True
    for record in calibration.to_dict("records"):
        fold=record["fold"]
        frame=saved[saved.fold==fold]
        month={"apr":4,"may":5,"jun":6,"aug":8}[fold]
        threshold=f"2024-{month:02d}-02T00:00:00Z"
        later=frame[frame.window_end_utc>=threshold]
        if record["scope"]=="headline":later=later[later.headline]
        pred="pred_raw" if record["model"]=="raw_recent_ridge" else "pred_offset"
        okay &= (len(later)==record["n"]
                 and abs(mean_absolute_error(later.SHAFT_MechPower_kW,later[pred])-record["mae_kw"])<1e-5
                 # Saved predictions are rounded to float32; allow its measured <3e-9 R2 delta.
                 and abs(r2_score(later.SHAFT_MechPower_kW,later[pred])-record["r2_score"])<1e-8)
    check("Offline first-day calibration scores exclude calibration-day labels and reproduce saved metrics",
          okay and len(calibration)==16,
          "Four folds, two scopes, raw and offset rows verified from saved predictions")
    limitation=json.loads((EX/"offline_calibration_limitation.json").read_text(encoding="utf-8"))
    check("Label-based offset experiment is explicitly marked nondeployable and excluded from ranking",
          "nondeployable" in limitation["status"] and "not ranked" in limitation["selection"],
          limitation["status"])
    out=ROOT/"v2_qa.csv"
    pd.DataFrame(ROWS).to_csv(out,index=False)
    counts=pd.DataFrame(ROWS).status.value_counts().to_dict()
    print(counts)
    if counts.get("FAIL",0):raise SystemExit(1)


if __name__=="__main__":main()
