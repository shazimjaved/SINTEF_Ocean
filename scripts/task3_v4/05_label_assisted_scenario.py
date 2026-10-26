"""Separate conditional scenario using delayed trustworthy power labels.

Reads saved V4 development predictions only; it does not refit models or use
December. At the start of each UTC day, a median residual is learned from the
three days ending *24 hours before that day*. Only prior positive-target
headline readings enter the correction. This requires operationally available,
trustworthy power readings and is never ranked with label-free models.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score

BASE=Path("outputs/task3_v4/models/predictions")
OUT=Path("outputs/task3_v4/label_assisted")
FOLDS=["apr","may","jun","aug"]
CANDIDATES=["B_ridge_head","D_ridge_head"]
MIN_TRUSTED=30
LOOKBACK_DAYS=3
LAG_DAYS=1


def metrics(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    return {"n":len(y),"mae_kw":float(mean_absolute_error(y,p)),
            "rmse_kw":float(np.sqrt(mean_squared_error(y,p))),
            "r2_score":float(r2_score(y,p)),
            "pearson_r":float(np.corrcoef(y,p)[0,1]) if np.ptp(p)>1e-10 else np.nan,
            "bias_kw":float(np.mean(y-p))}


def calibrate(frame,fold,candidate):
    d=frame.copy();d["ts"]=pd.to_datetime(d.window_end_utc,utc=True)
    d["day_start_utc"]=d.ts.dt.floor("D")
    d["offset_kw"]=0.0;d["trusted_history_n"]=0
    daily=[]
    for day in d.day_start_utc.unique():
        day=pd.Timestamp(day)
        latest=day-pd.Timedelta(days=LAG_DAYS)
        earliest=latest-pd.Timedelta(days=LOOKBACK_DAYS)
        history=d[(d.ts>=earliest)&(d.ts<latest)&d.headline]
        n=len(history)
        offset=float(np.median(history.actual_kw-history.predicted_kw)) if n>=MIN_TRUSTED else 0.0
        mask=d.day_start_utc==day
        d.loc[mask,"offset_kw"]=offset;d.loc[mask,"trusted_history_n"]=n
        daily.append({"fold":fold,"candidate":candidate,
                      "prediction_day_start_utc":day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "history_start_utc":earliest.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "history_exclusive_end_utc":latest.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "trusted_history_n":n,"offset_kw":offset,
                      "calibration_used":n>=MIN_TRUSTED,
                      "validation_minute_n":int(mask.sum())})
    d["prediction_assisted_kw"]=d.predicted_kw+d.offset_kw
    assert d.window_end_utc.is_unique
    return d,pd.DataFrame(daily)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/"label_assisted_development.csv"
    if target.exists():raise FileExistsError("Assisted scenario exists; preserve results")
    rows=[];days=[]
    for fold in FOLDS:
        for candidate in CANDIDATES:
            path=BASE/f"{fold}__{candidate}.csv.gz"
            if not path.exists():raise FileNotFoundError(path)
            saved=pd.read_csv(path)
            adjusted,daily=calibrate(saved,fold,candidate)
            days.append(daily)
            adjusted.drop(columns=["ts","day_start_utc"]).to_csv(
                OUT/f"{fold}__{candidate}__assisted.csv.gz",index=False,compression="gzip")
            for scope,part in [("headline",adjusted[adjusted.headline]),
                               ("broader_forward",adjusted)]:
                for scenario,col in [("A_label_free","predicted_kw"),
                                     ("B_delayed_label_assisted","prediction_assisted_kw")]:
                    rows.append({"fold":fold,"candidate":candidate,"scope":scope,
                                 "scenario":scenario,"trusted_history_min":MIN_TRUSTED,
                                 "label_lag_days":LAG_DAYS,"lookback_days":LOOKBACK_DAYS,
                                 "calibrated_minute_n":int(part.trusted_history_n.ge(MIN_TRUSTED).sum()),
                                 **metrics(part.actual_kw,part[col])})
            print(fold,candidate,"headline raw/assisted MAE",
                  rows[-4]["mae_kw"],rows[-3]["mae_kw"],flush=True)
    pd.DataFrame(rows).to_csv(target,index=False)
    pd.concat(days,ignore_index=True).to_csv(OUT/"daily_delayed_offsets.csv",index=False)
    manifest={"scenario":"conditional label-assisted, never ranked with label-free",
              "base_candidates":CANDIDATES,"folds":FOLDS,
              "prior_label_rule":"positive headline actual power only",
              "lag_days":LAG_DAYS,"lookback_days":LOOKBACK_DAYS,
              "minimum_trusted_labels":MIN_TRUSTED,
              "daily_rule":"history [day-4d, day-1d), correction set at UTC day start",
              "december":"not read","no_same_day_or_future_labels":True,
              "operational_status":"conditional; trustworthy power availability unverified"}
    (OUT/"scenario_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")


if __name__=="__main__":main()
