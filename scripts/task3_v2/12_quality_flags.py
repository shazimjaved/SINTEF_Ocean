"""Versioned V2 target-quality annotations, separate from model predictors.

These retrospective flags use observed target values. They are for label audit
and reporting, never inference-time eligibility or model input columns.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT=Path("outputs/task3_v2/data")
DATA=Path("outputs/task3/data")
TARGET="SHAFT_MechPower_kW"
COLS=["window_end_utc","source_month",TARGET,"target_n","target_min",
      "target_negative_n","STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct",
      "ME_ScavAirPressure_bar"]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=pd.concat([pd.read_csv(DATA/f"minute_2024_{m:02d}.csv.gz",usecols=COLS)
                     for m in range(1,13)],ignore_index=True)
    frame["target_observed"]=frame.target_n.gt(0)
    frame["forward_labelled"]=frame.target_observed&frame.STW_kn.ge(3)
    frame["target_zero_forward"]=frame.forward_labelled&frame[TARGET].eq(0)
    frame["engine_proxy_active"]=frame.ME_RPM_CAMS.gt(50)&frame.ME_FuelLoad_pct.gt(20)&frame.ME_ScavAirPressure_bar.gt(.5)
    frame["zero_forward_active_engine"]=frame.target_zero_forward&frame.engine_proxy_active
    frame["negative_raw_target"]=frame.forward_labelled&frame.target_negative_n.gt(0)
    frame["headline_eligible"]=frame.forward_labelled&frame[TARGET].gt(0)&frame.target_min.ge(0)&frame.target_negative_n.eq(0)
    # Consecutive zero-forward runs are computed on the full year, preserving
    # August/September and June/July continuations across file boundaries.
    ts=pd.to_datetime(frame.window_end_utc,utc=True)
    fresh=ts.diff().eq(pd.Timedelta(minutes=1))
    boundary=frame.target_zero_forward.ne(frame.target_zero_forward.shift(fill_value=False))|(~fresh)
    run_id=boundary.cumsum()
    lengths=frame.target_zero_forward.groupby(run_id).transform("sum")
    frame["zero_forward_run_minutes"]=np.where(frame.target_zero_forward,lengths,0).astype(np.int32)
    frame["long_zero_run_60min"]=frame.target_zero_forward&frame.zero_forward_run_minutes.ge(60)
    keep=["window_end_utc","source_month","target_observed","forward_labelled",
          "headline_eligible","target_zero_forward","engine_proxy_active",
          "zero_forward_active_engine","negative_raw_target",
          "zero_forward_run_minutes","long_zero_run_60min"]
    frame[keep].to_csv(OUT/"minute_label_quality_2024.csv.gz",index=False,compression="gzip")
    summary=frame.groupby("source_month").agg(calendar_minutes=("window_end_utc","size"),
          target_minutes=("target_observed","sum"),forward_labelled=("forward_labelled","sum"),
          headline_minutes=("headline_eligible","sum"),
          zero_forward=("target_zero_forward","sum"),
          zero_forward_active_engine=("zero_forward_active_engine","sum"),
          long_zero_run_minutes=("long_zero_run_60min","sum"),
          negative_raw_forward=("negative_raw_target","sum")).reset_index()
    summary.to_csv(OUT/"label_quality_monthly.csv",index=False)
    (OUT/"quality_flag_manifest.json").write_text(json.dumps({
        "version":"V2 diagnostic annotation",
        "source":"V1 completed-minute tables; no raw or V1 write",
        "target_dependent_flags":"all eligibility and zero-power flags are retrospective",
        "engine_active_definition":"CAMS RPM>50, fuel load>20%, scavenging pressure>0.5 bar; diagnostic only",
        "long_run_definition":"at least 60 consecutive completed minutes of zero target with STW>=3 kn",
        "model_input_status":"none of these target-derived fields may be used as predictors"},indent=2),encoding="utf-8")
    print({"rows":len(frame),"zero_forward_active_engine":int(frame.zero_forward_active_engine.sum()),
           "long_zero_run_minutes":int(frame.long_zero_run_60min.sum())})


if __name__=="__main__":main()
