"""Find positive-power training analogs for active-engine zero-power minutes.

This descriptive comparison does not relabel zeros or diagnose a sensor fault.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

OUT=Path("outputs/task3_v2/phase1")
DATA=Path("outputs/task3/data")
TARGET="SHAFT_MechPower_kW"
FEATURES=["STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar"]
READ=[TARGET,"target_n","target_min","target_negative_n"]+FEATURES


def load(months):
    return pd.concat([pd.read_csv(DATA/f"minute_2024_{m:02d}.csv.gz",usecols=READ)
                      for m in months],ignore_index=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    train=load(range(1,7))
    positive=(train.target_n.gt(0)&train.STW_kn.ge(3)&train[TARGET].gt(0)
              &train.target_min.ge(0)&train.target_negative_n.eq(0))
    reference=train.loc[positive,[TARGET]+FEATURES].dropna()
    median=reference[FEATURES].median()
    iqr=reference[FEATURES].quantile(.75)-reference[FEATURES].quantile(.25)
    x=((reference[FEATURES]-median)/iqr).to_numpy(dtype=np.float32)
    nn=NearestNeighbors(n_neighbors=5,n_jobs=1).fit(x)
    rows=[]
    for m in [6,8,9,11]:
        d=load([m])
        zero=(d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].eq(0)
              &d.ME_RPM_CAMS.gt(50)&d.ME_FuelLoad_pct.gt(20)
              &d.ME_ScavAirPressure_bar.gt(.5))
        frame=d.loc[zero,[TARGET]+FEATURES].dropna()
        if frame.empty: continue
        query=((frame[FEATURES]-median)/iqr).to_numpy(dtype=np.float32)
        dist,idx=nn.kneighbors(query)
        analog=reference[TARGET].to_numpy(dtype=np.float64)[idx].mean(axis=1)
        for caliper in [.5,1.0]:
            keep=dist[:,-1]<=caliper
            rows.append({"month":m,"caliper_iqr_units":caliper,
                         "active_zero_complete_n":len(frame),"matched_n":int(keep.sum()),
                         "matched_pct":100*keep.mean(),
                         "analog_positive_power_mean_kw":float(analog[keep].mean()) if keep.any() else np.nan,
                         "analog_positive_power_p10_kw":float(np.quantile(analog[keep],.1)) if keep.any() else np.nan,
                         "analog_positive_power_p90_kw":float(np.quantile(analog[keep],.9)) if keep.any() else np.nan})
    table=pd.DataFrame(rows)
    table.to_csv(OUT/"zero_power_positive_analogs.csv",index=False)
    print(table.round(2).to_string(index=False))


if __name__=="__main__":
    main()
