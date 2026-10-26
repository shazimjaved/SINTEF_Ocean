"""Can non-torquemeter onboard signals identify a recorded shaft-zero state?

The state is a retrospective *label*, never an input. Jan-Jun training and
August validation are chronological; July and December are not read. The
classifier is diagnostic and does not validate physical shaft status.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (average_precision_score,balanced_accuracy_score,
                             brier_score_loss,precision_score,recall_score,roc_auc_score)
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from channel_config import ANGLE_COLUMNS,COLUMN_TO_SOURCE,TARGET

DATA=Path("outputs/task3/data")
DYNAMIC=Path("outputs/task3_v3/model_features")
OUT=Path("outputs/task3_v4/state")
A={"STW_kn","SOG_kn","HULL_HeadingTrue_deg","HULL_TurnRate_degmin",
   "WIND_RelSpeed_kn","WIND_RelAngle_deg"}
B=A|{"ME_ScavAirPressure_bar","ME_TC_RPM_Transducer","ME_FuelLoad_pct","ME_RPM_CAMS"}
ENGINE=["STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar"]
ROLL=["STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar"]
DERIVED=["sog_minus_stw_kn","tc_over_cams","scav_over_fuel",
         "stw_cubed","cams_cubed","fuel_times_scav"]
HISTORY=[f"{col}__{stat}" for col in ROLL for stat in
         ["mean15","std15","mean60","std60","delta15"]]


def cols_for(channels):
    result=[]
    for col in sorted(channels):
        if col in ANGLE_COLUMNS:
            result += ["sin__"+col,"cos__"+col]
            if COLUMN_TO_SOURCE[col]=="onboard":result.append("resultant__"+col)
        else:result.append(col)
        result.append("n__"+col)
    return result


COLS_A=cols_for(A)
COLS_B=cols_for(B)
FEATURE_SETS={"A_restricted":COLS_A,"B_engine":COLS_B,
              "B_engine_history":COLS_B+DERIVED+HISTORY}
READ=sorted(set(COLS_B+["window_end_utc",TARGET,"target_n","target_min",
                         "target_negative_n"]))


def load(month):
    dtype={c:"float32" for c in READ if c not in {"window_end_utc","target_n","target_negative_n"}}
    dtype.update(target_n="int16",target_negative_n="int16")
    d=pd.read_csv(DATA/f"minute_2024_{month:02d}.csv.gz",usecols=READ,dtype=dtype)
    if month in {1,2,3,4,5,6,8}:
        extra=pd.read_csv(DYNAMIC/f"dynamic_2024_{month:02d}.csv.gz")
        if not d.window_end_utc.equals(extra.window_end_utc):raise ValueError("Dynamic timestamp mismatch")
        d=pd.concat([d,extra[DERIVED+HISTORY]],axis=1)
    active=(d.ME_RPM_CAMS.gt(50)&d.ME_FuelLoad_pct.gt(20)
            &d.ME_ScavAirPressure_bar.gt(.5))
    observed=d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].notna()&active
    positive=observed&d[TARGET].gt(0)&d.target_min.ge(0)&d.target_negative_n.eq(0)
    zero=observed&d[TARGET].eq(0)
    chosen=positive|zero
    d=d.loc[chosen].copy()
    d["recorded_zero_state"]=zero[chosen].to_numpy(dtype=bool)
    return d


def model():
    return make_pipeline(SimpleImputer(strategy="median",add_indicator=True,
                                       keep_empty_features=True),
        HistGradientBoostingClassifier(max_iter=100,learning_rate=.07,
              max_leaf_nodes=15,min_samples_leaf=100,l2_regularization=2.0,
              early_stopping=False,random_state=4259))


def classify(train,valid):
    rows=[];predictions=[]
    y=train.recorded_zero_state.to_numpy(dtype=bool)
    v=valid.recorded_zero_state.to_numpy(dtype=bool)
    if y.sum()<100 or v.sum()<100:raise ValueError("Insufficient recorded-zero examples")
    # Positive class weight is fitted entirely from Jan-Jun state prevalence.
    prevalence=y.mean()
    weights=np.where(y,1/(2*prevalence),1/(2*(1-prevalence))).astype(np.float32)
    for name,cols in FEATURE_SETS.items():
        assert all("SHAFT_" not in col and not col.startswith("target") for col in cols)
        estimator=model();start=time.perf_counter()
        estimator.fit(train[cols].to_numpy(dtype=np.float32),y,
                      histgradientboostingclassifier__sample_weight=weights)
        fit_seconds=time.perf_counter()-start
        prob=estimator.predict_proba(valid[cols].to_numpy(dtype=np.float32))[:,1]
        pred=prob>=.5
        rows.append({"feature_set":name,"train_n":len(y),"train_zero_n":int(y.sum()),
                     "validation_n":len(v),"validation_zero_n":int(v.sum()),
                     "train_zero_prevalence":float(prevalence),
                     "validation_zero_prevalence":float(v.mean()),
                     "roc_auc":float(roc_auc_score(v,prob)),
                     "average_precision":float(average_precision_score(v,prob)),
                     "balanced_accuracy_at_05":float(balanced_accuracy_score(v,pred)),
                     "precision_at_05":float(precision_score(v,pred,zero_division=0)),
                     "recall_at_05":float(recall_score(v,pred,zero_division=0)),
                     "brier_score":float(brier_score_loss(v,prob)),
                     "zero_probability_median":float(np.median(prob[v])),
                     "positive_probability_median":float(np.median(prob[~v])),
                     "fit_seconds":round(fit_seconds,3)})
        predictions.append(pd.DataFrame({"window_end_utc":valid.window_end_utc,
                                         "recorded_zero_state":v,"feature_set":name,
                                         "predicted_zero_probability":prob}))
        print(name,rows[-1],flush=True)
    return pd.DataFrame(rows),pd.concat(predictions,ignore_index=True)


def same_month_overlap(month,frame,train_scale):
    positive=frame[~frame.recorded_zero_state][ENGINE].dropna()
    zero=frame[frame.recorded_zero_state][ENGINE].dropna()
    med=train_scale[ENGINE].median()
    iqr=train_scale[ENGINE].quantile(.75)-train_scale[ENGINE].quantile(.25)
    if iqr.le(0).any():raise ValueError("Zero train IQR")
    x=((positive-med)/iqr).to_numpy(dtype=np.float32)
    y=((zero-med)/iqr).to_numpy(dtype=np.float32)
    distances,_=NearestNeighbors(n_neighbors=5,n_jobs=1).fit(x).kneighbors(y)
    return [{"month":month,"caliper_train_iqr":c,"zero_complete_n":len(y),
             "positive_complete_n":len(x),"zero_with_5_positive_analogs_n":int((distances[:,-1]<=c).sum()),
             "overlap_pct":100*float((distances[:,-1]<=c).mean()),
             "fifth_neighbor_distance_median":float(np.median(distances[:,-1]))}
            for c in [.1,.25,.5]]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    destination=OUT/"august_state_identifiability.csv"
    if destination.exists():raise FileExistsError("V4 state experiment exists; preserve it")
    monthly={m:load(m) for m in [1,2,3,4,5,6,8]}
    train=pd.concat([monthly[m] for m in range(1,7)],ignore_index=True)
    valid=monthly[8]
    metrics,predictions=classify(train,valid)
    metrics.to_csv(destination,index=False)
    predictions.to_csv(OUT/"august_state_probabilities.csv.gz",index=False,compression="gzip")
    overlaps=same_month_overlap(6,monthly[6],train)
    overlaps+=same_month_overlap(8,monthly[8],train)
    pd.DataFrame(overlaps).to_csv(OUT/"same_month_zero_positive_overlap.csv",index=False)
    manifest={"train_months":[1,2,3,4,5,6],"validation_month":8,
              "target_derived_state":"retrospective label only; never a predictor",
              "state_definition":"observed zero power at STW>=3, CAMS RPM>50, fuel load>20, scav pressure>0.5",
              "controls":"positive power, same active-engine and forward rules",
              "feature_sets":FEATURE_SETS,"noon":"excluded: issue time unknown",
              "torquemeter_predictors":"none","threshold":.5,
              "zero_class_weights":"training prevalence only"}
    (OUT/"state_experiment_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(pd.DataFrame(overlaps).to_string(index=False),flush=True)


if __name__=="__main__":main()
