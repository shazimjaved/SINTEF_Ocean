"""Offline first-day intercept-calibration upper bound on development folds.

Requires trustworthy labelled shaft power in the first 24h of each validation
month. Such availability is unverified, so this is NOT a deployable model and
is never ranked against label-free candidates. December is never loaded.
"""
import json
import runpy
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

OUT=Path("outputs/task3_v2/experiments")
CODE=runpy.run_path("scripts/task3_v2/07_walkforward_experiments.py")
COLS=CODE["COLS"]["B"]
TARGET=CODE["TARGET"]
FOLDS=CODE["FOLDS"]
load=CODE["load"]
mask=CODE["mask"]


def score(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    return {"n":len(y),"mae_kw":float(mean_absolute_error(y,p)),
            "rmse_kw":float(np.sqrt(mean_squared_error(y,p))),
            "r2_score":float(r2_score(y,p)),"pearson_r":float(np.corrcoef(y,p)[0,1]),
            "bias_kw":float((y-p).mean())}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"offline_calibration_upper_bound.csv"
    if path.exists():raise FileExistsError("Calibration diagnostic already exists; preserve history")
    needed=sorted({m for _,train,val in FOLDS for m in train+[val]})
    assert 12 not in needed
    monthly={m:load(m) for m in needed}
    rows=[]
    saved=[]
    for fold,months,val_month in FOLDS:
        train=pd.concat([monthly[m] for m in months],ignore_index=True)
        start=pd.Timestamp(2024,val_month,1,tz="UTC")
        cutoff=(start-pd.Timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        train=train.loc[mask(train)&train.window_end_utc.ge(cutoff)]
        pipeline=make_pipeline(SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True),
                               StandardScaler(),Ridge(alpha=100.0))
        pipeline.fit(train[COLS].to_numpy(dtype=np.float32),train[TARGET].to_numpy(dtype=np.float32))
        val=monthly[val_month].loc[mask(monthly[val_month],broad=True)].copy()
        val["pred_raw"]=pipeline.predict(val[COLS].to_numpy(dtype=np.float32))
        val["headline"]=mask(val)
        first_day_end=(start+pd.Timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        calibration=val[val.headline&val.window_end_utc.lt(first_day_end)]
        if len(calibration)<120:raise ValueError(f"Too few first-day headline labels for {fold}")
        correction=float(np.median(calibration[TARGET]-calibration.pred_raw))
        val["pred_offset"]=val.pred_raw+correction
        test=val[val.window_end_utc.ge(first_day_end)]
        for scope,part in [("headline",test[test.headline]),("broader_forward",test)]:
            for model,pred in [("raw_recent_ridge","pred_raw"),("first_day_offset_upper_bound","pred_offset")]:
                rows.append({"fold":fold,"scope":scope,"model":model,
                             "calibration_day_headline_n":len(calibration),
                             "calibration_offset_kw":correction,
                             "calibration_window":"first 24 calendar hours; scored later minutes only",
                             **score(part[TARGET],part[pred])})
        saved.append(val[["window_end_utc",TARGET,"pred_raw","pred_offset","headline"]].assign(fold=fold))
    table=pd.DataFrame(rows)
    table.to_csv(path,index=False)
    pd.concat(saved,ignore_index=True).to_csv(OUT/"offline_calibration_predictions.csv.gz",
                                               index=False,compression="gzip")
    (OUT/"offline_calibration_limitation.json").write_text(json.dumps({
        "status":"nondeployable diagnostic upper bound",
        "requires":"first-day trustworthy target labels and verified timing",
        "selection":"not ranked with label-free candidates; no December used"},indent=2),encoding="utf-8")
    subset=table[table.scope=="headline"]
    fig,ax=plt.subplots(figsize=(8,4))
    pivot=subset.pivot(index="fold",columns="model",values="mae_kw")
    pivot.plot.bar(ax=ax,color=["#35b779","#31688e"])
    ax.set(ylabel="Later-period headline MAE (kW)",xlabel="Validation month",
           title="Diagnostic first-day offset using known labels")
    ax.tick_params(axis="x",rotation=0)
    fig.tight_layout()
    fig.savefig(OUT/"offline_calibration_upper_bound.png",dpi=180)
    plt.close(fig)
    print(subset[["fold","model","n","mae_kw","r2_score","calibration_offset_kw"]].round(2).to_string(index=False))


if __name__=="__main__":main()
