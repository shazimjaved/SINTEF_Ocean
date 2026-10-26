"""Independent V4 QA: timing, provenance, scope and saved-prediction metrics."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score,mean_absolute_error,
                             mean_squared_error,r2_score,roc_auc_score)

ROOT=Path("outputs/task3_v4")
ROWS=[]


def check(identifier,claim,passed,evidence):
    ROWS.append({"id":identifier,"claim":claim,"status":"PASS" if passed else "FAIL",
                 "evidence":str(evidence)})


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda:file.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def score(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    return {"n":len(y),"mae_kw":mean_absolute_error(y,p),
            "rmse_kw":np.sqrt(mean_squared_error(y,p)),
            "r2_score":r2_score(y,p),
            "pearson_r":np.corrcoef(y,p)[0,1] if np.ptp(p)>1e-10 else np.nan,
            "bias_kw":np.mean(y-p)}


def close_metrics(record,actual):
    return (record["n"]==actual["n"] and all(
        np.isclose(record[name],actual[name],atol=1e-7,rtol=1e-9,equal_nan=True)
        for name in ["mae_kw","rmse_kw","r2_score","pearson_r","bias_kw"]))


def main():
    frozen=json.loads(Path("outputs/task3/tables/frozen_artifact_sha256.json").read_text())
    check("V4Q01","V1 frozen model, selection, predictions and metrics retain original hashes",
          all(digest(path)==hashvalue for path,hashvalue in frozen.items()),
          f"{len(frozen)} frozen files")
    prior=pd.read_csv("outputs/task3_v3/v3_qa.csv")
    check("V4Q02","Preserved V3 QA evidence remains complete",
          len(prior)==17 and prior.status.eq("PASS").all(),f"V3 QA rows={len(prior)}")
    noon=pd.read_csv(ROOT/"noon/noon_schema_and_timing.csv")
    eligibility=pd.read_csv(ROOT/"noon/noon_feature_eligibility.csv")
    loading=pd.read_csv(ROOT/"noon/noon_loading_monthly_descriptive.csv")
    check("V4Q03","Noon files are date-only and lack measurement/issuance columns",
          len(noon)==12 and noon.rows.sum()==366
          and noon.time_or_issue_columns.isna().all()
          and eligibility.ranked_model_status.str.startswith("excluded").all(),
          "366 dated rows; no issue-time field")
    check("V4Q04","August Noon displacement is constant, not a within-month state indicator",
          int(loading.loc[loading.month==8,"displacement_distinct_values"].iloc[0])==1,
          "August distinct displacement values=1")
    state_manifest=json.loads((ROOT/"state/state_experiment_manifest.json").read_text())
    state=pd.read_csv(ROOT/"state/august_state_identifiability.csv")
    proba=pd.read_csv(ROOT/"state/august_state_probabilities.csv.gz")
    features=[c for cols in state_manifest["feature_sets"].values() for c in cols]
    check("V4Q05","State labels are retrospective outputs; all classifier inputs are onboard and target-free",
          state_manifest["train_months"]==[1,2,3,4,5,6]
          and state_manifest["validation_month"]==8
          and all("SHAFT_" not in c and not c.startswith("target") for c in features),
          f"feature sets={len(state_manifest['feature_sets'])}")
    state_ok=True
    for record in state.to_dict("records"):
        part=proba[proba.feature_set==record["feature_set"]]
        y=part.recorded_zero_state.to_numpy(dtype=bool)
        p=part.predicted_zero_probability.to_numpy(dtype=np.float64)
        state_ok &= (len(part)==record["validation_n"]
                     and y.sum()==record["validation_zero_n"]
                     and abs(roc_auc_score(y,p)-record["roc_auc"])<1e-10
                     and abs(average_precision_score(y,p)-record["average_precision"])<1e-10)
    check("V4Q06","August state AUC and average precision recompute from saved probabilities",
          state_ok and len(state)==3,"Three independent onboard feature sets")
    overlap=pd.read_csv(ROOT/"state/same_month_zero_positive_overlap.csv")
    check("V4Q07","Zero-versus-positive same-month analog counts have valid denominators",
          len(overlap)==6 and set(overlap.month)=={6,8}
          and overlap.zero_with_5_positive_analogs_n.le(overlap.zero_complete_n).all(),
          f"June/August overlap rows={len(overlap)}")
    onset=pd.read_csv(ROOT/"state/august_onset_probability_summary.csv")
    check("V4Q08","State onset analysis uses saved August predictions and separate before/after windows",
          len(onset)==9 and onset[onset.phase=="before10"].observed_zero_n.eq(0).all()
          and onset[onset.phase=="after10"].observed_zero_n.eq(10).all(),
          "3 feature sets × 3 fixed windows")
    manifest=json.loads((ROOT/"models/v4_boosting_manifest.json").read_text())
    folds=manifest["folds"]
    months={m for _,training,val in folds for m in training+[val]}
    check("V4Q09","All boosting folds are chronological and exclude July, November and December",
          months=={1,2,3,4,5,6,8} and len(folds)==4
          and all(max(training)<val for _,training,val in folds)
          and manifest["no_december"] and manifest["no_validation_label_fit_or_calibration"],
          folds)
    predictor_cols=[c for cols in manifest["feature_columns"].values() for c in cols]
    check("V4Q10","Ranked predictors exclude target, torquemeter and Noon Report fields",
          all("SHAFT_" not in c and not c.startswith("target") and "draft" not in c.lower()
              and "displacement" not in c.lower() for c in predictor_cols),
          f"A/B/D input columns={list(map(len,manifest['feature_columns'].values()))}")
    models=pd.read_csv(ROOT/"models/v4_boosting_development.csv")
    candidates={c["name"] for c in manifest["candidates"]}
    pred_paths=list((ROOT/"models/predictions").glob("*.csv.gz"))
    check("V4Q11","Every candidate-fold has a saved broad prediction file and two score scopes",
          len(candidates)==15 and len(pred_paths)==60 and len(models)==120
          and models.groupby(["fold","candidate"]).scope.nunique().eq(2).all(),
          f"prediction files={len(pred_paths)}; scores={len(models)}")
    metric_ok=True;alignment_ok=True
    expected={"apr":(42465,42468),"may":(17851,17903),
              "jun":(12084,30112),"aug":(35086,41205)}
    reference={}
    for fold,month in [("apr",4),("may",5),("jun",6),("aug",8)]:
        source=pd.read_csv(Path("outputs/task3/data")/f"minute_2024_{month:02d}.csv.gz",
                           usecols=["window_end_utc","SHAFT_MechPower_kW","target_n","STW_kn"])
        source=source[source.target_n.gt(0)&source.STW_kn.ge(3)
                      &source.SHAFT_MechPower_kW.notna()].reset_index(drop=True)
        reference[fold]=source
    for fold in expected:
        for candidate in candidates:
            frame=pd.read_csv(ROOT/"models/predictions"/f"{fold}__{candidate}.csv.gz")
            alignment_ok &= (frame.window_end_utc.is_unique
                             and len(frame)==expected[fold][1]
                             and int(frame.headline.sum())==expected[fold][0]
                             and frame.window_end_utc.equals(reference[fold].window_end_utc)
                             and np.allclose(frame.actual_kw,
                                             reference[fold].SHAFT_MechPower_kW,
                                             atol=.02,rtol=2e-6))
            for scope,part in [("headline",frame[frame.headline]),
                               ("broader_forward",frame)]:
                record=models[(models.fold==fold)&(models.candidate==candidate)
                              &(models.scope==scope)].iloc[0].to_dict()
                metric_ok &= close_metrics(record,score(part.actual_kw,part.predicted_kw))
    check("V4Q12","Saved prediction timestamps and headline/broader counts reconcile by fold",
          alignment_ok,"60 files across four months")
    check("V4Q13","All MAE, RMSE, R2, Pearson r and bias values recompute exactly from saved predictions",
          metric_ok,"120 model-fold-scope rows")
    assisted_manifest=json.loads((ROOT/"label_assisted/scenario_manifest.json").read_text())
    assisted=pd.read_csv(ROOT/"label_assisted/label_assisted_development.csv")
    daily=pd.read_csv(ROOT/"label_assisted/daily_delayed_offsets.csv")
    check("V4Q14","Label-assisted scenario is separate, delayed and excludes December",
          assisted_manifest["december"]=="not read"
          and assisted_manifest["no_same_day_or_future_labels"]
          and assisted_manifest["lag_days"]==1
          and len(assisted)==4*2*2*2,
          f"rows={len(assisted)}")
    time_ok=True;offset_ok=True
    for row in daily.itertuples():
        day=pd.Timestamp(row.prediction_day_start_utc)
        latest=pd.Timestamp(row.history_exclusive_end_utc)
        earliest=pd.Timestamp(row.history_start_utc)
        time_ok &= (latest<=day-pd.Timedelta(days=1)
                    and earliest==latest-pd.Timedelta(days=3))
        frame=pd.read_csv(ROOT/"models/predictions"/f"{row.fold}__{row.candidate}.csv.gz")
        ts=pd.to_datetime(frame.window_end_utc,utc=True)
        old=frame[(ts>=earliest)&(ts<latest)&frame.headline]
        expected_offset=float(np.median(old.actual_kw-old.predicted_kw)) if len(old)>=30 else 0.0
        offset_ok &= (len(old)==row.trusted_history_n
                      and abs(expected_offset-row.offset_kw)<1e-8)
    check("V4Q15","Every assisted offset uses only eligible observations at least one day old",
          time_ok and offset_ok,f"daily offset rows={len(daily)}")
    assisted_ok=True
    for row in assisted.to_dict("records"):
        frame=pd.read_csv(ROOT/"label_assisted"/
                          f"{row['fold']}__{row['candidate']}__assisted.csv.gz")
        if row["scope"]=="headline":frame=frame[frame.headline]
        col="predicted_kw" if row["scenario"]=="A_label_free" else "prediction_assisted_kw"
        assisted_ok &= close_metrics(row,score(frame.actual_kw,frame[col]))
        assisted_ok &= np.allclose(frame.prediction_assisted_kw,
                                  frame.predicted_kw+frame.offset_kw,atol=1e-8)
    check("V4Q16","Separate assisted-scenario metrics reproduce saved minute predictions",
          assisted_ok,"32 scope-scenario rows")
    output=ROOT/"v4_qa.csv"
    pd.DataFrame(ROWS).to_csv(output,index=False)
    status=pd.DataFrame(ROWS).status.value_counts().to_dict()
    print(status)
    if status.get("FAIL",0):raise SystemExit(1)


if __name__=="__main__":main()
