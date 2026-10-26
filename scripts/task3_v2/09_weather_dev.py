"""Development-only retrospective provider-weather sensitivity experiments.

Provider issue-time semantics remain unknown. December is never loaded.
"""
import json
import runpy
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

OUT=Path("outputs/task3_v2/experiments")
sys.path.insert(0,str(Path("scripts").resolve()))
COMMON=runpy.run_path("scripts/12_task3_train_validate.py")
COLS=COMMON["columns_for"](COMMON["FEATURE_SETS"]["C_exploratory_weather"])
LOAD=COMMON["load_months"]
MASK=COMMON["label_mask"]
TARGET=COMMON["TARGET"]
FOLDS=[("apr",[1,2,3],4),("may",[1,2,3,4],5),
       ("jun",[1,2,3,4,5],6),("aug",[1,2,3,4,5,6],8)]
CASES=[("C_hgb_full","hgb","full"),("C_hgb_recent90","hgb","recent90"),
       ("C_ridge_recent90","ridge","recent90")]


def score(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    return {"n":len(y),"mae_kw":float(mean_absolute_error(y,p)),
            "rmse_kw":float(np.sqrt(mean_squared_error(y,p))),
            "pearson_r":float(np.corrcoef(y,p)[0,1]) if np.ptp(p)>1e-10 else np.nan,
            "r2_score":float(r2_score(y,p)),"bias_kw":float(np.mean(y-p))}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"v2_weather_development.csv"
    if path.exists():raise FileExistsError("Weather development output exists; preserve experiment history")
    months=sorted({m for _,train,val in FOLDS for m in train+[val]})
    assert 12 not in months and 7 not in months and 11 not in months
    monthly={m:LOAD([m]) for m in months}
    rows=[]
    for name,train_months,val_month in FOLDS:
        train=pd.concat([monthly[m] for m in train_months],ignore_index=True)
        validation=monthly[val_month]
        for case,family,window in CASES:
            eligible=train.loc[MASK(train)].copy()
            if window=="recent90":
                start=pd.Timestamp(2024,val_month,1,tz="UTC")
                cutoff=(start-pd.Timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
                eligible=eligible[eligible.window_end_utc>=cutoff]
            imputer=SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True)
            if family=="hgb":
                learner=HistGradientBoostingRegressor(max_iter=120,learning_rate=.07,
                    max_leaf_nodes=31,min_samples_leaf=80,l2_regularization=1.0,
                    early_stopping=False,random_state=4259)
                model=make_pipeline(imputer,learner)
            else:model=make_pipeline(imputer,StandardScaler(),Ridge(alpha=100.0))
            t0=time.perf_counter()
            model.fit(eligible[COLS].to_numpy(dtype=np.float32),
                      eligible[TARGET].to_numpy(dtype=np.float32))
            fit_seconds=time.perf_counter()-t0
            broad=validation.loc[MASK(validation,broad=True)].copy()
            broad["prediction"]=model.predict(broad[COLS].to_numpy(dtype=np.float32))
            broad["headline"]=MASK(broad)
            for scope,part in [("headline",broad[broad.headline]),("broader_forward",broad)]:
                rows.append({"fold":name,"candidate":case,"scope":scope,
                             "train_n":len(eligible),"fit_seconds":round(fit_seconds,3),
                             **score(part[TARGET],part.prediction)})
            pd.DataFrame(rows).to_csv(path,index=False)
            print(name,case,rows[-2]["mae_kw"],rows[-2]["r2_score"],flush=True)
    pd.DataFrame(rows).to_csv(path,index=False)
    (OUT/"v2_weather_caveat.json").write_text(json.dumps({
        "status":"retrospective only",
        "reason":"provider raw timestamps may denote weather validity rather than issuance",
        "selection_data":"April, May, June, August; never December",
        "model_families":["Ridge","HistGradientBoostingRegressor"]},indent=2),encoding="utf-8")


if __name__=="__main__":main()
