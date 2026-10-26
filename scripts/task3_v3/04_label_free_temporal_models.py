"""Development-only label-free onboard feature experiment.

Every rolling feature uses the current completed minute and earlier minutes;
none uses future windows, target values, torquemeter channels, July, November,
December, external provider timing, or validation labels during fitting.
Imputation and scaling are fitted inside each chronological training fold.
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
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from channel_config import ANGLE_COLUMNS,COLUMN_TO_SOURCE,TARGET

DATA=Path("outputs/task3/data")
OUT=Path("outputs/task3_v3/models")
FEATURE_OUT=Path("outputs/task3_v3/model_features")
FOLDS=[("apr",[1,2,3],4),("may",[1,2,3,4],5),
       ("jun",[1,2,3,4,5],6),("aug",[1,2,3,4,5,6],8)]
A={"STW_kn","SOG_kn","HULL_HeadingTrue_deg","HULL_TurnRate_degmin",
   "WIND_RelSpeed_kn","WIND_RelAngle_deg"}
B=A|{"ME_ScavAirPressure_bar","ME_TC_RPM_Transducer",
     "ME_FuelLoad_pct","ME_RPM_CAMS"}
ROLL=["STW_kn","SOG_kn","ME_RPM_CAMS","ME_FuelLoad_pct",
      "ME_ScavAirPressure_bar","ME_TC_RPM_Transducer"]
DERIVED=["sog_minus_stw_kn","tc_over_cams","scav_over_fuel",
         "stw_cubed","cams_cubed","fuel_times_scav"]
ROLL_COLS=[f"{col}__{stat}" for col in ROLL for stat in
           ["mean15","std15","mean60","std60","delta15"]]
CANDIDATES=[
    {"name":"B_derived_ridge_recent90","group":"B","kind":"ridge","window":"recent90","derived":True,"rolling":False},
    {"name":"B_dynamic_ridge_recent90","group":"B","kind":"ridge","window":"recent90","derived":True,"rolling":True},
    {"name":"B_dynamic_hgb_recent90","group":"B","kind":"hgb","window":"recent90","derived":True,"rolling":True},
    {"name":"B_dynamic_hgb_full","group":"B","kind":"hgb","window":"full","derived":True,"rolling":True},
]


def cols_for(channels):
    cols=[]
    for col in sorted(channels):
        if col in ANGLE_COLUMNS:
            cols.extend(["sin__"+col,"cos__"+col])
            if COLUMN_TO_SOURCE[col]=="onboard":cols.append("resultant__"+col)
        else:cols.append(col)
        cols.append("n__"+col)
    return cols


BASE_COLS=cols_for(B)
READ=sorted(set(BASE_COLS+["window_end_utc",TARGET,"target_n","target_min",
                           "target_negative_n"]))


def load_derive(month):
    dtypes={c:"float32" for c in READ if c not in {"window_end_utc","target_n","target_negative_n"}}
    dtypes.update(target_n="int16",target_negative_n="int16")
    frame=pd.read_csv(DATA/f"minute_2024_{month:02d}.csv.gz",usecols=READ,dtype=dtypes)
    assert len(frame) in {41760,43200,44640} and frame.window_end_utc.is_unique
    add=pd.DataFrame({"window_end_utc":frame.window_end_utc})
    add["sog_minus_stw_kn"]=(frame.SOG_kn-frame.STW_kn).astype(np.float32)
    add["tc_over_cams"]=(frame.ME_TC_RPM_Transducer/
                           frame.ME_RPM_CAMS.where(frame.ME_RPM_CAMS.gt(1))).astype(np.float32)
    add["scav_over_fuel"]=(frame.ME_ScavAirPressure_bar/
                             frame.ME_FuelLoad_pct.where(frame.ME_FuelLoad_pct.gt(1))).astype(np.float32)
    add["stw_cubed"]=(frame.STW_kn**3).astype(np.float32)
    add["cams_cubed"]=(frame.ME_RPM_CAMS**3).astype(np.float32)
    add["fuel_times_scav"]=(frame.ME_FuelLoad_pct*frame.ME_ScavAirPressure_bar).astype(np.float32)
    for col in ROLL:
        series=frame[col]
        w15=series.rolling(15,min_periods=5)
        w60=series.rolling(60,min_periods=20)
        add[f"{col}__mean15"]=w15.mean().astype(np.float32)
        add[f"{col}__std15"]=w15.std().astype(np.float32)
        add[f"{col}__mean60"]=w60.mean().astype(np.float32)
        add[f"{col}__std60"]=w60.std().astype(np.float32)
        add[f"{col}__delta15"]=(series-add[f"{col}__mean15"]).astype(np.float32)
    assert add.window_end_utc.equals(frame.window_end_utc)
    destination=FEATURE_OUT/f"dynamic_2024_{month:02d}.csv.gz"
    add.to_csv(destination,index=False,compression="gzip")
    return pd.concat([frame,add.drop(columns="window_end_utc")],axis=1)


def mask(d,broad=False):
    base=d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].notna()
    if broad:return base
    return base&d[TARGET].gt(0)&d.target_min.ge(0)&d.target_negative_n.eq(0)


def columns(candidate):
    cols=BASE_COLS.copy()
    if candidate["derived"]:cols.extend(DERIVED)
    if candidate["rolling"]:cols.extend(ROLL_COLS)
    return cols


def model(candidate):
    imputer=SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True)
    if candidate["kind"]=="ridge":
        return make_pipeline(imputer,StandardScaler(),Ridge(alpha=100))
    return make_pipeline(imputer,HistGradientBoostingRegressor(
        max_iter=120,learning_rate=.07,max_leaf_nodes=31,min_samples_leaf=80,
        l2_regularization=1.0,early_stopping=False,random_state=4259))


def metric(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    if not len(y) or not np.isfinite(p).all():raise ValueError("Invalid predictions")
    return {"n":len(y),"mae_kw":float(mean_absolute_error(y,p)),
            "rmse_kw":float(np.sqrt(mean_squared_error(y,p))),
            "pearson_r":float(np.corrcoef(y,p)[0,1]) if np.ptp(p)>1e-10 else np.nan,
            "r2_score":float(r2_score(y,p)),"bias_kw":float(np.mean(y-p))}


def main():
    OUT.mkdir(parents=True,exist_ok=True);FEATURE_OUT.mkdir(parents=True,exist_ok=True)
    destination=OUT/"v3_label_free_development.csv"
    if destination.exists() or any(FEATURE_OUT.glob("dynamic_2024_*.csv.gz")):
        raise FileExistsError("V3 results already exist; preserve experiment history")
    months=sorted({m for _,training,val in FOLDS for m in training+[val]})
    assert 12 not in months and 7 not in months and 11 not in months
    monthly={m:load_derive(m) for m in months}
    manifest={"folds":FOLDS,"candidates":CANDIDATES,"no_december":True,
              "prediction_time":"end of completed minute",
              "rolling_rule":"current and prior 14 or 59 completed minutes; per-month reset",
              "no_label_calibration":True,"no_torquemeter_predictors":True,
              "weather_provider_channels":"excluded"}
    (OUT/"v3_label_free_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    rows=[]
    for fold,training,val in FOLDS:
        train=pd.concat([monthly[m] for m in training],ignore_index=True)
        valid=monthly[val]
        broad=valid.loc[mask(valid,broad=True)].copy()
        broad["headline"]=mask(broad)
        for candidate in CANDIDATES:
            selected=train.loc[mask(train)].copy()
            if candidate["window"]=="recent90":
                start=pd.Timestamp(2024,val,1,tz="UTC")
                cutoff=(start-pd.Timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
                selected=selected[selected.window_end_utc>=cutoff]
            cols=columns(candidate)
            x=selected[cols].to_numpy(dtype=np.float32)
            y=selected[TARGET].to_numpy(dtype=np.float32)
            estimator=model(candidate)
            t0=time.perf_counter();estimator.fit(x,y);elapsed=time.perf_counter()-t0
            prediction=estimator.predict(broad[cols].to_numpy(dtype=np.float32))
            for scope,keep in [("headline",broad.headline.to_numpy()),
                               ("broader_forward",np.ones(len(broad),dtype=bool))]:
                rows.append({"fold":fold,"validation_month":val,
                             "candidate":candidate["name"],"scope":scope,
                             "train_n":len(selected),"feature_n":len(cols),
                             "fit_seconds":round(elapsed,3),
                             **metric(broad.loc[keep,TARGET],prediction[keep])})
            print(fold,candidate["name"],rows[-2]["mae_kw"],rows[-2]["r2_score"],flush=True)
    result=pd.DataFrame(rows)
    result.to_csv(destination,index=False)
    baseline=pd.read_csv("outputs/task3_v2/experiments/v2_walkforward_results.csv")
    baseline=baseline[baseline.candidate.isin(["B_ridge_recent90","B_hgb_recent90"])].copy()
    common=["fold","candidate","scope","n","mae_kw","rmse_kw","pearson_r","r2_score","bias_kw"]
    compare=pd.concat([baseline[common],result[common]],ignore_index=True)
    compare.to_csv(OUT/"v3_development_with_v2_baselines.csv",index=False)
    summary=compare[compare.scope=="headline"].groupby("candidate").agg(
        mean_fold_mae_kw=("mae_kw","mean"),worst_fold_mae_kw=("mae_kw","max"),
        worst_fold_r2=("r2_score","min")).sort_values("mean_fold_mae_kw")
    summary.to_csv(OUT/"v3_development_summary.csv")
    print(summary.to_string(),flush=True)


if __name__=="__main__":main()
