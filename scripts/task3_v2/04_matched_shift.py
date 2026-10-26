"""Feature-space matching and simple relationship-shift diagnostics.

Nearest-neighbor matching uses January-June headline rows as the reference.
December is descriptive only. No V1 model is loaded, fitted or selected.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

OUT = Path("outputs/task3_v2/phase1")
DATA = Path("outputs/task3/data")
TARGET = "SHAFT_MechPower_kW"
BASE = ["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
EXTENDED = BASE + ["SOG_kn", "ME_TC_RPM_Transducer"]
READ = [TARGET, "target_n", "target_min", "target_negative_n"] + EXTENDED


def load(months):
    frames = [pd.read_csv(DATA / f"minute_2024_{m:02d}.csv.gz", usecols=READ) for m in months]
    frame = pd.concat(frames, ignore_index=True)
    keep = (frame.target_n.gt(0) & frame.STW_kn.ge(3) & frame[TARGET].gt(0)
            & frame.target_min.ge(0) & frame.target_negative_n.eq(0))
    return frame.loc[keep].reset_index(drop=True)


def match(train, other, period, cols, caliper):
    t = train[[TARGET]+cols].dropna()
    o = other[[TARGET]+cols].dropna()
    med = t[cols].median()
    iqr = t[cols].quantile(.75) - t[cols].quantile(.25)
    if iqr.le(0).any():
        raise ValueError("Zero-IQR matching feature")
    x_train = ((t[cols]-med)/iqr).to_numpy(dtype=np.float32)
    x_other = ((o[cols]-med)/iqr).to_numpy(dtype=np.float32)
    nn = NearestNeighbors(n_neighbors=5, algorithm="auto", n_jobs=1).fit(x_train)
    distances, indexes = nn.kneighbors(x_other)
    # All five analogs must be near; prevents one distant training state from
    # setting a reference target. The caliper is diagnostic, not tuned on test.
    accepted = distances[:, -1] <= caliper
    target_analog = t[TARGET].to_numpy(dtype=np.float64)[indexes].mean(axis=1)
    target_other = o[TARGET].to_numpy(dtype=np.float64)
    delta = target_other - target_analog
    selected = delta[accepted]
    return {"period": period, "features": "+".join(cols), "caliper_iqr_units": caliper,
            "complete_case_n": len(o), "matched_n": int(accepted.sum()),
            "matched_pct_complete": 100*accepted.mean(),
            "mean_neighbor5_distance": float(distances[accepted].mean()) if accepted.any() else np.nan,
            "target_minus_train_analog_mean_kw": float(selected.mean()) if len(selected) else np.nan,
            "target_minus_train_analog_median_kw": float(np.median(selected)) if len(selected) else np.nan,
            "target_minus_train_analog_p10_kw": float(np.quantile(selected,.1)) if len(selected) else np.nan,
            "target_minus_train_analog_p90_kw": float(np.quantile(selected,.9)) if len(selected) else np.nan}


def simple_pressure_relation(train, others):
    relation = []
    fitted = {}
    for period, frame in [("jan_jun_train", train)] + list(others.items()):
        pair = frame[[TARGET,"ME_ScavAirPressure_bar"]].dropna()
        x = pair.ME_ScavAirPressure_bar.to_numpy(dtype=np.float64)
        y = pair[TARGET].to_numpy(dtype=np.float64)
        slope = float(np.cov(x,y,ddof=0)[0,1]/np.var(x))
        intercept = float(y.mean()-slope*x.mean())
        relation.append({"period":period,"n":len(pair),"intercept_kw":intercept,
                         "slope_kw_per_bar":slope,"pearson_r":float(np.corrcoef(x,y)[0,1]),
                         "target_mean_kw":float(y.mean()),"pressure_mean_bar":float(x.mean())})
        fitted[period]=(intercept,slope)
    a,b=fitted["jan_jun_train"]
    for row in relation:
        period=row["period"]
        frame=train if period=="jan_jun_train" else others[period]
        pair=frame[[TARGET,"ME_ScavAirPressure_bar"]].dropna()
        pred=a+b*pair.ME_ScavAirPressure_bar.to_numpy(dtype=np.float64)
        y=pair[TARGET].to_numpy(dtype=np.float64)
        row["train_relation_mean_bias_kw"] = float((y-pred).mean())
        row["train_relation_mae_kw"] = float(np.abs(y-pred).mean())
        row["train_relation_pearson_r"] = float(np.corrcoef(y,pred)[0,1])
    return pd.DataFrame(relation)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    train=load(range(1,7))
    other={"august":load([8]),"september":load([9]),"october":load([10]),
           "december_diagnostic":load([12])}
    rows=[]
    for name,frame in other.items():
        for cols in [BASE,EXTENDED]:
            for caliper in [.5,1.0]:
                rows.append(match(train,frame,name,cols,caliper))
    match_table=pd.DataFrame(rows)
    match_table.to_csv(OUT/"nearest_neighbor_shift.csv",index=False)
    pressure=simple_pressure_relation(train,other)
    pressure.to_csv(OUT/"pressure_relation_shift.csv",index=False)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    subset=match_table[(match_table.features=="+".join(BASE))&(match_table.caliper_iqr_units==.5)]
    bars=axes[0].bar(subset.period,subset.target_minus_train_analog_mean_kw,color="#3b528b")
    for bar,n in zip(bars,subset.matched_n):
        axes[0].annotate(f"n={n:,}",(bar.get_x()+bar.get_width()/2,bar.get_height()),
                         xytext=(0,-15),textcoords="offset points",ha="center",fontsize=8)
    axes[0].tick_params(axis="x",rotation=25)
    axes[0].set(title="Target difference from near training analogs",ylabel="Mean difference (kW)")
    axes[1].plot(pressure.period,pressure.train_relation_mean_bias_kw,marker="o")
    axes[1].tick_params(axis="x",rotation=25)
    axes[1].set(title="Train-fitted pressure relation transfer",ylabel="Observed minus predicted (kW)")
    fig.tight_layout()
    fig.savefig(OUT/"matched_and_pressure_shift.png",dpi=180)
    plt.close(fig)
    print(match_table[(match_table.features=="+".join(BASE))
                      &(match_table.caliper_iqr_units==.5)][[
                          "period","matched_n","matched_pct_complete",
                          "target_minus_train_analog_mean_kw"]].to_string(index=False))
    print(pressure[["period","n","pearson_r","train_relation_mean_bias_kw"]].to_string(index=False))


if __name__=="__main__":
    main()
