"""Diagnostic-only matched torque/RPM comparison across development folds.

Torquemeter channels here explain the *label*; they never enter prediction.
Neighbor selection uses only four onboard non-target features, fit to earlier
months. No December data is used.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

DATA=Path("outputs/task3/data")
AUDIT=Path("outputs/task3_v3/zero_states/torquemeter_minute_audit_2024.csv.gz")
OUT=Path("outputs/task3_v3/cross_period")
TARGET="SHAFT_MechPower_kW"
FEATURES=["STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar"]
FOLDS=[("apr",[1,2,3],4),("may",[1,2,3,4],5),
       ("jun",[1,2,3,4,5],6),("aug",[1,2,3,4,5,6],8)]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    audit=pd.read_csv(AUDIT,usecols=["window_end_utc","source_month","SHAFT_RPM_TQ",
                                    "SHAFT_Torque_Nm_TQ"])
    months={m for _,tr,val in FOLDS for m in tr+[val]}
    assert months=={1,2,3,4,5,6,8}
    monthly={}
    for month in sorted(months):
        d=pd.read_csv(DATA/f"minute_2024_{month:02d}.csv.gz",
                      usecols=["window_end_utc",TARGET,"target_n","target_min",
                               "target_negative_n"]+FEATURES)
        a=audit[audit.source_month==month].reset_index(drop=True)
        assert d.window_end_utc.equals(a.window_end_utc)
        d["shaft_rpm_diagnostic"]=a.SHAFT_RPM_TQ.to_numpy()
        d["torque_diagnostic"]=a.SHAFT_Torque_Nm_TQ.to_numpy()
        keep=d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].gt(0)&d.target_min.ge(0)&d.target_negative_n.eq(0)
        monthly[month]=d.loc[keep].reset_index(drop=True)
    del audit
    rows=[]
    for fold,training,val in FOLDS:
        train=pd.concat([monthly[m] for m in training],ignore_index=True)
        valid=monthly[val]
        fields=FEATURES+[TARGET,"torque_diagnostic","shaft_rpm_diagnostic"]
        t=train[fields].dropna();v=valid[fields].dropna()
        med=t[FEATURES].median();iqr=t[FEATURES].quantile(.75)-t[FEATURES].quantile(.25)
        x=((t[FEATURES]-med)/iqr).to_numpy(dtype=np.float32)
        y=((v[FEATURES]-med)/iqr).to_numpy(dtype=np.float32)
        nn=NearestNeighbors(n_neighbors=5,n_jobs=1).fit(x)
        distances,index=nn.kneighbors(y)
        for caliper in [.5,1.0]:
            keep=distances[:,-1]<=caliper
            if not keep.any():continue
            row={"fold":fold,"caliper_train_iqr":caliper,"train_n":len(t),
                 "validation_complete_n":len(v),"matched_n":int(keep.sum()),
                 "matched_pct":100*keep.mean()}
            for col,short in [(TARGET,"power_kw"),("torque_diagnostic","torque_numeric"),
                              ("shaft_rpm_diagnostic","shaft_rpm")]:
                reference=t[col].to_numpy(dtype=np.float64)[index].mean(axis=1)[keep]
                observed=v[col].to_numpy(dtype=np.float64)[keep]
                row[f"train_analog_{short}_mean"]=float(reference.mean())
                row[f"validation_{short}_mean"]=float(observed.mean())
                row[f"validation_minus_analog_{short}"]=float((observed-reference).mean())
                row[f"validation_over_analog_{short}_ratio"]=float(observed.mean()/reference.mean())
            rows.append(row)
    result=pd.DataFrame(rows)
    result.to_csv(OUT/"fold_matched_torque_rpm_diagnostic.csv",index=False)
    print(result[["fold","caliper_train_iqr","matched_n",
                  "validation_minus_analog_power_kw","validation_minus_analog_torque_numeric",
                  "validation_minus_analog_shaft_rpm","validation_over_analog_torque_numeric_ratio",
                  "validation_over_analog_shaft_rpm_ratio"]].to_string(index=False))


if __name__=="__main__":main()
