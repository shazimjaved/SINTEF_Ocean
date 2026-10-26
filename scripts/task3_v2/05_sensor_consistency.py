"""Compare target and non-target sensor relationships across periods.

All regressions are descriptive, fitted on January-June only for transfer
residuals. No December-based model selection or V1 artifact modification.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance

OUT=Path("outputs/task3_v2/phase1")
DATA=Path("outputs/task3/data")
TARGET="SHAFT_MechPower_kW"
VARS=[TARGET,"STW_kn","SOG_kn","ME_RPM_CAMS","ME_FuelLoad_pct",
      "ME_ScavAirPressure_bar","ME_TC_RPM_Transducer"]
READ=VARS+["target_n","target_min","target_negative_n"]
PAIRS=[
    (TARGET,"ME_ScavAirPressure_bar"),(TARGET,"ME_FuelLoad_pct"),(TARGET,"ME_RPM_CAMS"),
    ("ME_ScavAirPressure_bar","ME_FuelLoad_pct"),
    ("ME_ScavAirPressure_bar","ME_RPM_CAMS"),
    ("ME_FuelLoad_pct","ME_RPM_CAMS"),
    ("ME_TC_RPM_Transducer","ME_ScavAirPressure_bar"),
]


def load(months):
    d=pd.concat([pd.read_csv(DATA/f"minute_2024_{m:02d}.csv.gz",usecols=READ)
                 for m in months],ignore_index=True)
    rule=(d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].gt(0)
          &d.target_min.ge(0)&d.target_negative_n.eq(0))
    return d.loc[rule].reset_index(drop=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    periods={"jan_jun_train":load(range(1,7)),"august":load([8]),
             "september":load([9]),"october":load([10]),
             "december_diagnostic":load([12])}
    train=periods["jan_jun_train"]
    rows=[]
    for response,predictor in PAIRS:
        paired=train[[response,predictor]].dropna()
        tx=paired[predictor].to_numpy(dtype=np.float64)
        ty=paired[response].to_numpy(dtype=np.float64)
        slope=np.cov(tx,ty,ddof=0)[0,1]/np.var(tx)
        intercept=ty.mean()-slope*tx.mean()
        scale=float(np.std(ty))
        for name,frame in periods.items():
            pair=frame[[response,predictor]].dropna()
            x=pair[predictor].to_numpy(dtype=np.float64)
            y=pair[response].to_numpy(dtype=np.float64)
            pred=intercept+slope*x
            residual=y-pred
            rows.append({"response":response,"predictor":predictor,"period":name,
                         "n":len(pair),"train_slope":slope,"train_intercept":intercept,
                         "response_train_std":scale,
                         "mean_residual":float(residual.mean()),
                         "mean_residual_in_train_sd":float(residual.mean()/scale),
                         "mae":float(np.abs(residual).mean()),
                         "within_period_pearson_r":float(np.corrcoef(x,y)[0,1]),
                         "within_period_slope":float(np.cov(x,y,ddof=0)[0,1]/np.var(x))})
    pd.DataFrame(rows).to_csv(OUT/"sensor_relationship_transfer.csv",index=False)
    distribution=[]
    for name,frame in periods.items():
        if name=="jan_jun_train": continue
        for col in VARS:
            t=train[col].dropna().to_numpy(dtype=np.float64)
            o=frame[col].dropna().to_numpy(dtype=np.float64)
            distribution.append({"period":name,"variable":col,"train_n":len(t),
                                 "period_n":len(o),"train_mean":float(t.mean()),
                                 "period_mean":float(o.mean()),
                                 "mean_difference":float(o.mean()-t.mean()),
                                 "ks_distance":float(ks_2samp(t,o,method="asymp").statistic),
                                 "wasserstein_distance":float(wasserstein_distance(t,o))})
    pd.DataFrame(distribution).to_csv(OUT/"distribution_shift_effect_sizes.csv",index=False)
    print(pd.DataFrame(rows).query("period != 'jan_jun_train'")[[
        "response","predictor","period","mean_residual","mean_residual_in_train_sd"]].round(3).to_string(index=False))


if __name__=="__main__":
    main()
