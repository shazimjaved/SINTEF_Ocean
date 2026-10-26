"""Bounded CPU comparison of Ridge, HGB, XGBoost, LightGBM and CatBoost.

Only chronological development folds Apr/May/Jun/Aug are used. December is
never read. No validation target is passed to fit, early stopping, calibration
or hyperparameter selection. Every candidate predicts all broader-forward
minutes; headline and broader scores are saved separately.
"""
import json
import os
import platform
import sys
import time
from pathlib import Path

import catboost
import lightgbm
import numpy as np
import pandas as pd
import sklearn
import xgboost
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from channel_config import ANGLE_COLUMNS,COLUMN_TO_SOURCE,TARGET

DATA=Path("outputs/task3/data")
DYNAMIC=Path("outputs/task3_v3/model_features")
OUT=Path("outputs/task3_v4/models")
PRED=OUT/"predictions"
FOLDS=[("apr",[1,2,3],4),("may",[1,2,3,4],5),
       ("jun",[1,2,3,4,5],6),("aug",[1,2,3,4,5,6],8)]
A={"STW_kn","SOG_kn","HULL_HeadingTrue_deg","HULL_TurnRate_degmin",
   "WIND_RelSpeed_kn","WIND_RelAngle_deg"}
B=A|{"ME_ScavAirPressure_bar","ME_TC_RPM_Transducer",
     "ME_FuelLoad_pct","ME_RPM_CAMS"}
DERIVED=["sog_minus_stw_kn","tc_over_cams","scav_over_fuel",
         "stw_cubed","cams_cubed","fuel_times_scav"]
ROLL=["STW_kn","SOG_kn","ME_RPM_CAMS","ME_FuelLoad_pct",
      "ME_ScavAirPressure_bar","ME_TC_RPM_Transducer"]
HISTORY=[f"{col}__{stat}" for col in ROLL for stat in
         ["mean15","std15","mean60","std60","delta15"]]
NAMES=[
    ("A_hgb_head","A","hgb","headline"),("A_lgbm_head","A","lgbm","headline"),
    ("B_ridge_head","B","ridge","headline"),("B_hgb_head","B","hgb","headline"),
    ("B_xgb_head","B","xgb","headline"),("B_lgbm_head","B","lgbm","headline"),
    ("B_cat_head","B","cat","headline"),
    ("D_ridge_head","D","ridge","headline"),("D_hgb_head","D","hgb","headline"),
    ("D_xgb_head","D","xgb","headline"),("D_lgbm_head","D","lgbm","headline"),
    ("D_cat_head","D","cat","headline"),
    ("B_hgb_broad","B","hgb","broader"),("B_lgbm_broad","B","lgbm","broader"),
    ("D_xgb_broad","D","xgb","broader"),
]
CANDIDATES=[{"name":name,"group":group,"family":family,"training_labels":labels}
            for name,group,family,labels in NAMES]


def cols_for(channels):
    out=[]
    for col in sorted(channels):
        if col in ANGLE_COLUMNS:
            out.extend(["sin__"+col,"cos__"+col])
            if COLUMN_TO_SOURCE[col]=="onboard":out.append("resultant__"+col)
        else:out.append(col)
        out.append("n__"+col)
    return out


COLS={"A":cols_for(A),"B":cols_for(B),"D":cols_for(B)+DERIVED+HISTORY}
READ=sorted(set(COLS["B"]+["window_end_utc",TARGET,"target_n","target_min",
                           "target_negative_n"]))


def load(month):
    dtype={c:"float32" for c in READ if c not in {"window_end_utc","target_n","target_negative_n"}}
    dtype.update(target_n="int16",target_negative_n="int16")
    frame=pd.read_csv(DATA/f"minute_2024_{month:02d}.csv.gz",usecols=READ,dtype=dtype)
    extra=pd.read_csv(DYNAMIC/f"dynamic_2024_{month:02d}.csv.gz",
                      usecols=["window_end_utc"]+DERIVED+HISTORY,
                      dtype={c:"float32" for c in DERIVED+HISTORY})
    if not frame.window_end_utc.equals(extra.window_end_utc):
        raise ValueError("Dynamic minute timestamps not aligned")
    return pd.concat([frame,extra.drop(columns="window_end_utc")],axis=1)


def mask(d,broader=False):
    base=d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].notna()
    if broader:return base
    return base&d[TARGET].gt(0)&d.target_min.ge(0)&d.target_negative_n.eq(0)


def estimator(family):
    if family=="ridge":
        return make_pipeline(SimpleImputer(strategy="median",add_indicator=True,
                                           keep_empty_features=True),
                             StandardScaler(),Ridge(alpha=100.0))
    if family=="hgb":
        return make_pipeline(SimpleImputer(strategy="median",add_indicator=True,
                                           keep_empty_features=True),
              HistGradientBoostingRegressor(max_iter=120,learning_rate=.07,
                  max_leaf_nodes=31,min_samples_leaf=80,l2_regularization=1.0,
                  early_stopping=False,random_state=4259))
    if family=="xgb":
        return XGBRegressor(n_estimators=220,max_depth=4,learning_rate=.05,
              subsample=.85,colsample_bytree=.85,min_child_weight=50,
              reg_lambda=10,objective="reg:squarederror",tree_method="hist",
              device="cpu",n_jobs=2,random_state=4259)
    if family=="lgbm":
        return LGBMRegressor(n_estimators=220,max_depth=6,num_leaves=31,
              learning_rate=.05,min_child_samples=100,reg_lambda=10,n_jobs=2,
              random_state=4259,verbosity=-1)
    if family=="cat":
        return CatBoostRegressor(iterations=220,depth=6,learning_rate=.05,
              l2_leaf_reg=10,loss_function="RMSE",thread_count=2,task_type="CPU",
              random_seed=4259,verbose=False,allow_writing_files=False)
    raise ValueError(family)


def scores(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    if not len(y) or not np.isfinite(p).all():raise ValueError("Invalid predictions")
    return {"n":len(y),"mae_kw":float(mean_absolute_error(y,p)),
            "rmse_kw":float(np.sqrt(mean_squared_error(y,p))),
            "r2_score":float(r2_score(y,p)),
            "pearson_r":float(np.corrcoef(y,p)[0,1]) if np.ptp(p)>1e-10 else np.nan,
            "bias_kw":float(np.mean(y-p))}


def fit_predict(train,valid,fold,val_month,candidate):
    pred_path=PRED/f"{fold}__{candidate['name']}.csv.gz"
    meta_path=Path(str(pred_path)+".meta.json")
    if pred_path.exists():
        saved=pd.read_csv(pred_path)
        if not saved.window_end_utc.equals(valid.window_end_utc):
            raise ValueError("Saved prediction timestamps changed")
        meta=json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return saved,float(meta.get("fit_seconds",float("nan"))),True
    selected=train.loc[mask(train,broader=candidate["training_labels"]=="broader")]
    start=pd.Timestamp(2024,val_month,1,tz="UTC")
    cutoff=(start-pd.Timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    selected=selected[selected.window_end_utc>=cutoff]
    cols=COLS[candidate["group"]]
    assert all("SHAFT_" not in col and not col.startswith("target") for col in cols)
    x=selected[cols].to_numpy(dtype=np.float32)
    y=selected[TARGET].to_numpy(dtype=np.float32)
    xv=valid[cols].to_numpy(dtype=np.float32)
    if np.isinf(x).any() or np.isinf(xv).any():raise ValueError("Infinite feature")
    model=estimator(candidate["family"])
    t0=time.perf_counter();model.fit(x,y);fit_seconds=time.perf_counter()-t0
    prediction=model.predict(xv)
    saved=pd.DataFrame({"window_end_utc":valid.window_end_utc,
                        "actual_kw":valid[TARGET].to_numpy(dtype=np.float64),
                        "predicted_kw":np.asarray(prediction,dtype=np.float64),
                        "headline":mask(valid).to_numpy(dtype=bool)})
    tmp=pred_path.with_suffix(".csv.gz.tmp")
    saved.to_csv(tmp,index=False,compression="gzip")
    os.replace(tmp,pred_path)
    meta_path.write_text(json.dumps({"fit_seconds":fit_seconds,"train_n":len(selected),
                                     "feature_n":len(cols),"family":candidate["family"]},indent=2))
    return saved,fit_seconds,False


def main():
    OUT.mkdir(parents=True,exist_ok=True);PRED.mkdir(parents=True,exist_ok=True)
    months=sorted({m for _,training,val in FOLDS for m in training+[val]})
    assert months==[1,2,3,4,5,6,8]
    manifest={"folds":[[fold,training,val] for fold,training,val in FOLDS],
              "candidates":CANDIDATES,"feature_columns":COLS,
              "training_window":"prior 90 calendar days within permitted training months",
              "no_validation_label_fit_or_calibration":True,"no_december":True,
              "headline":"positive target, no negative raw target, STW>=3",
              "broader_forward":"all observed targets at STW>=3, including zeros/negative",
              "threads_per_booster":2,"software":{
                  "python":platform.python_version(),"sklearn":sklearn.__version__,
                  "xgboost":xgboost.__version__,"lightgbm":lightgbm.__version__,
                  "catboost":catboost.__version__}}
    manifest_path=OUT/"v4_boosting_manifest.json"
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if old!=manifest:raise ValueError("Experiment manifest changed; use a new version")
    else:manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    data={m:load(m) for m in months}
    rows=[]
    for fold,training,val in FOLDS:
        train=pd.concat([data[m] for m in training],ignore_index=True)
        valid=data[val].loc[mask(data[val],broader=True)].reset_index(drop=True)
        for candidate in CANDIDATES:
            saved,fit_seconds,reused=fit_predict(train,valid,fold,val,candidate)
            for scope,part in [("headline",saved[saved.headline]),
                               ("broader_forward",saved)]:
                rows.append({"fold":fold,"validation_month":val,
                             "candidate":candidate["name"],"feature_group":candidate["group"],
                             "family":candidate["family"],"training_labels":candidate["training_labels"],
                             "scope":scope,"fit_seconds":round(fit_seconds,3),
                             "reused_saved_prediction":reused,
                             **scores(part.actual_kw,part.predicted_kw)})
            pd.DataFrame(rows).to_csv(OUT/"v4_boosting_development.csv",index=False)
            print(fold,candidate["name"],f"MAE={rows[-2]['mae_kw']:.1f}",
                  f"R2={rows[-2]['r2_score']:.3f}","reused" if reused else "fit",flush=True)
    result=pd.DataFrame(rows)
    headline=result[result.scope=="headline"]
    rank=headline.groupby("candidate").agg(mean_fold_mae_kw=("mae_kw","mean"),
              worst_fold_mae_kw=("mae_kw","max"),worst_fold_r2=("r2_score","min"),
              mean_abs_bias_kw=("bias_kw",lambda x:np.abs(x).mean())).sort_values(
                  ["worst_fold_mae_kw","mean_fold_mae_kw"])
    rank.to_csv(OUT/"v4_development_stability.csv")
    print(rank.to_string(),flush=True)


if __name__=="__main__":main()
