"""Versioned V2 development-only walk-forward model comparison.

No December file or V1 fitted model is opened. Folds are Apr, May, Jun, Aug;
July is quarantined. Candidate definitions and equal-fold ranking are fixed in
this source before execution. Outputs are internal experimental evidence.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_config import ANGLE_COLUMNS, COLUMN_TO_SOURCE, TARGET

OUT=Path("outputs/task3_v2/experiments")
DATA=Path("outputs/task3/data")
A={"STW_kn","SOG_kn","HULL_HeadingTrue_deg","HULL_TurnRate_degmin",
   "WIND_RelSpeed_kn","WIND_RelAngle_deg"}
B=A|{"ME_ScavAirPressure_bar","ME_TC_RPM_Transducer","ME_FuelLoad_pct","ME_RPM_CAMS"}
FOLDS=[("apr",[1,2,3],4),("may",[1,2,3,4],5),
       ("jun",[1,2,3,4,5],6),("aug",[1,2,3,4,5,6],8)]
CANDIDATES=[
    {"name":"A_hgb_full_v1like","group":"A","family":"hgb","window":"full","loss":"squared_error","labels":"headline","decay":None},
    {"name":"A_hgb_recent90","group":"A","family":"hgb","window":"recent90","loss":"squared_error","labels":"headline","decay":None},
    {"name":"B_hgb_full","group":"B","family":"hgb","window":"full","loss":"squared_error","labels":"headline","decay":None},
    {"name":"B_hgb_recent90","group":"B","family":"hgb","window":"recent90","loss":"squared_error","labels":"headline","decay":None},
    {"name":"B_hgb_decay60","group":"B","family":"hgb","window":"full","loss":"squared_error","labels":"headline","decay":60},
    {"name":"B_hgb_recent90_absolute","group":"B","family":"hgb","window":"recent90","loss":"absolute_error","labels":"headline","decay":None},
    {"name":"B_ridge_full","group":"B","family":"ridge","window":"full","loss":"squared_error","labels":"headline","decay":None},
    {"name":"B_ridge_recent90","group":"B","family":"ridge","window":"recent90","loss":"squared_error","labels":"headline","decay":None},
    {"name":"B_hgb_broad_full","group":"B","family":"hgb","window":"full","loss":"squared_error","labels":"broad","decay":None},
]


def cols_for(channels):
    cols=[]
    for col in sorted(channels):
        if col in ANGLE_COLUMNS:
            cols.extend(["sin__"+col,"cos__"+col])
            if COLUMN_TO_SOURCE[col]=="onboard": cols.append("resultant__"+col)
        else: cols.append(col)
        cols.append("n__"+col if COLUMN_TO_SOURCE[col]=="onboard" else "age_s__"+col)
    return cols


COLS={"A":cols_for(A),"B":cols_for(B)}
READ=sorted(set(COLS["B"]+["window_end_utc",TARGET,"target_n","target_min",
                           "target_negative_n","STW_kn"]))


def load(m):
    dtype={c:"float32" for c in READ if c not in {"window_end_utc","target_n","target_negative_n"}}
    dtype["target_n"]="int16"; dtype["target_negative_n"]="int16"
    return pd.read_csv(DATA/f"minute_2024_{m:02d}.csv.gz",usecols=READ,dtype=dtype)


def mask(d,broad=False):
    base=d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].notna()
    if broad:return base
    return base&d[TARGET].gt(0)&d.target_min.ge(0)&d.target_negative_n.eq(0)


def model(candidate):
    imputer=SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True)
    if candidate["family"]=="ridge":
        return make_pipeline(imputer,StandardScaler(),Ridge(alpha=100.0))
    leaves=15 if candidate["group"]=="A" else 31
    return make_pipeline(imputer,HistGradientBoostingRegressor(
        loss=candidate["loss"],max_iter=120,learning_rate=.07,
        max_leaf_nodes=leaves,min_samples_leaf=80,l2_regularization=1.0,
        early_stopping=False,random_state=4259))


def scores(y,pred):
    y=np.asarray(y,dtype=np.float64);pred=np.asarray(pred,dtype=np.float64)
    if len(y)==0 or not np.isfinite(pred).all():raise ValueError("Invalid evaluation")
    r=np.nan if np.ptp(pred)<1e-10 else float(np.corrcoef(y,pred)[0,1])
    return {"n":len(y),"mae_kw":float(mean_absolute_error(y,pred)),
            "rmse_kw":float(np.sqrt(mean_squared_error(y,pred))),
            "pearson_r":r,"r2_score":float(r2_score(y,pred)),
            "bias_kw":float(np.mean(y-pred))}


def fit_score(candidate,fold_name,train_raw,val_raw,val_month):
    start=pd.Timestamp(2024,val_month,1,tz="UTC")
    chosen=train_raw.loc[mask(train_raw,broad=candidate["labels"]=="broad")].copy()
    if candidate["window"]=="recent90":
        cutoff=(start-pd.Timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        chosen=chosen[chosen.window_end_utc>=cutoff]
    if len(chosen)<5000:raise ValueError(f"Too few training rows for {candidate['name']} {fold_name}")
    cols=COLS[candidate["group"]]
    x=chosen[cols].to_numpy(dtype=np.float32)
    y=chosen[TARGET].to_numpy(dtype=np.float32)
    pipeline=model(candidate)
    t0=time.perf_counter()
    if candidate["decay"]:
        age=(start-pd.to_datetime(chosen.window_end_utc,utc=True)).dt.total_seconds().to_numpy()/86400
        weights=np.power(.5,age/candidate["decay"]).astype(np.float32)
        pipeline.fit(x,y,histgradientboostingregressor__sample_weight=weights)
    else:pipeline.fit(x,y)
    fit_seconds=time.perf_counter()-t0
    broad=val_raw.loc[mask(val_raw,broad=True)].copy()
    broad["pred"] = pipeline.predict(broad[cols].to_numpy(dtype=np.float32))
    broad["headline"] = mask(broad)
    result=[]
    for scope,part in [("headline",broad[broad.headline]),("broader_forward",broad)]:
        result.append({"fold":fold_name,"validation_month":val_month,
                       "candidate":candidate["name"],"feature_group":candidate["group"],
                       "training_labels":candidate["labels"],"training_window":candidate["window"],
                       "train_n":len(chosen),"fit_seconds":round(fit_seconds,3),
                       "scope":scope,**scores(part[TARGET],part.pred)})
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    existing=OUT/"v2_walkforward_results.csv"
    if existing.exists():raise FileExistsError("V2 results already exist; preserve experiment history")
    needed=sorted({m for _,months,val in FOLDS for m in months+[val]})
    assert 12 not in needed and 7 not in needed and 11 not in needed
    monthly={m:load(m) for m in needed}
    manifest={"folds":FOLDS,"candidates":CANDIDATES,
              "selection_data":"April, May, June, August only; no December",
              "primary_scope":"predeclared V1 headline; broader forward also reported",
              "ranking":"equal-fold mean headline MAE plus worst-fold and R2 diagnostics"}
    (OUT/"v2_experiment_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    rows=[]
    for fold,months,val in FOLDS:
        train=pd.concat([monthly[m] for m in months],ignore_index=True)
        validation=monthly[val]
        for candidate in CANDIDATES:
            record=fit_score(candidate,fold,train,validation,val)
            rows.extend(record)
            pd.DataFrame(rows).to_csv(existing,index=False)
            print(fold,candidate["name"],record[0]["mae_kw"],record[0]["r2_score"],flush=True)
    result=pd.DataFrame(rows)
    head=result[result.scope=="headline"]
    rank=head.groupby("candidate").agg(mean_mae_kw=("mae_kw","mean"),
        median_mae_kw=("mae_kw","median"),worst_mae_kw=("mae_kw","max"),
        mean_r2=("r2_score","mean"),worst_r2=("r2_score","min"),
        mean_abs_bias_kw=("bias_kw",lambda x:np.abs(x).mean()),
        total_fit_seconds=("fit_seconds","sum")).sort_values("mean_mae_kw").reset_index()
    rank.to_csv(OUT/"v2_development_ranking.csv",index=False)
    print("RANKING",rank.to_string(index=False),flush=True)


if __name__=="__main__":
    main()
