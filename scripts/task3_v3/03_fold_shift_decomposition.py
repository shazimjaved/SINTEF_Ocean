"""Development-only composition versus conditional-target shift diagnostics.

Reference distributions, scales, neighbors and regime clusters are fit to each
fold's earlier-period training data. December is not read. Positive-target
headline rows are used for the conditional comparisons; broader-scope counts
are shown separately and no label is used as a model feature.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.neighbors import NearestNeighbors

DATA=Path("outputs/task3/data")
OUT=Path("outputs/task3_v3/cross_period")
TARGET="SHAFT_MechPower_kW"
FEATURES=["STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar"]
EXTRA=["SOG_kn","ME_TC_RPM_Transducer","WIND_RelSpeed_kn","HULL_TurnRate_degmin"]
FOLDS=[("apr",[1,2,3],4),("may",[1,2,3,4],5),
       ("jun",[1,2,3,4,5],6),("aug",[1,2,3,4,5,6],8)]
READ=[TARGET,"target_n","target_min","target_negative_n"]+FEATURES+EXTRA


def load(month):
    d=pd.read_csv(DATA/f"minute_2024_{month:02d}.csv.gz",usecols=READ)
    base=d.target_n.gt(0)&d.STW_kn.ge(3)&d[TARGET].notna()
    head=base&d[TARGET].gt(0)&d.target_min.ge(0)&d.target_negative_n.eq(0)
    d=d[base].copy();d["headline"]=head[base].to_numpy()
    return d


def matched(train,valid,fold,columns):
    t=train[train.headline][[TARGET]+columns].dropna()
    v=valid[valid.headline][[TARGET]+columns].dropna()
    med=t[columns].median();iqr=t[columns].quantile(.75)-t[columns].quantile(.25)
    if iqr.le(0).any():raise ValueError("Zero train IQR")
    xt=((t[columns]-med)/iqr).to_numpy(dtype=np.float32)
    xv=((v[columns]-med)/iqr).to_numpy(dtype=np.float32)
    nearest=NearestNeighbors(n_neighbors=5,n_jobs=1).fit(xt)
    distance,index=nearest.kneighbors(xv)
    analog=t[TARGET].to_numpy(dtype=np.float64)[index].mean(axis=1)
    truth=v[TARGET].to_numpy(dtype=np.float64)
    rows=[]
    for caliper in [.5,1.0]:
        keep=distance[:,-1]<=caliper
        base_mean=float(t[TARGET].mean())
        reference=float(analog[keep].mean()) if keep.any() else np.nan
        observed=float(truth[keep].mean()) if keep.any() else np.nan
        rows.append({"fold":fold,"features":"+".join(columns),"caliper_train_iqr":caliper,
                     "train_headline_complete_n":len(t),"validation_headline_complete_n":len(v),
                     "matched_n":int(keep.sum()),"matched_pct":100*keep.mean(),
                     "train_unconditional_mean_kw":base_mean,
                     "matched_train_analog_mean_kw":reference,
                     "matched_validation_mean_kw":observed,
                     "composition_component_kw":reference-base_mean,
                     "conditional_component_kw":observed-reference,
                     "matched_total_shift_kw":observed-base_mean,
                     "conditional_median_kw":float(np.median((truth-analog)[keep])) if keep.any() else np.nan})
    return rows


def clusters(train,valid,fold):
    cols=FEATURES+["SOG_kn","ME_TC_RPM_Transducer"]
    t=train[train.headline][[TARGET]+cols].dropna()
    v=valid[valid.headline][[TARGET]+cols].dropna()
    med=t[cols].median();iqr=t[cols].quantile(.75)-t[cols].quantile(.25)
    if iqr.le(0).any():raise ValueError("Zero train IQR")
    xt=((t[cols]-med)/iqr).to_numpy(dtype=np.float32)
    xv=((v[cols]-med)/iqr).to_numpy(dtype=np.float32)
    model=MiniBatchKMeans(n_clusters=8,batch_size=2048,n_init=3,random_state=4259)
    tc=model.fit_predict(xt);vc=model.predict(xv)
    rows=[]
    for k in range(8):
        yt=t[TARGET].to_numpy()[tc==k]
        yv=v[TARGET].to_numpy()[vc==k]
        rows.append({"fold":fold,"cluster":k,"train_n":len(yt),"validation_n":len(yv),
                     "train_share_pct":100*len(yt)/len(t),"validation_share_pct":100*len(yv)/len(v),
                     "train_mean_kw":float(np.mean(yt)) if len(yt) else np.nan,
                     "validation_mean_kw":float(np.mean(yv)) if len(yv) else np.nan,
                     "within_cluster_shift_kw":float(np.mean(yv)-np.mean(yt))
                                                if len(yt) and len(yv) else np.nan})
    return rows


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    months=sorted({m for _,train,val in FOLDS for m in train+[val]})
    assert 12 not in months and 7 not in months and 11 not in months
    data={m:load(m) for m in months}
    matching=[];regimes=[];coverage=[]
    for fold,training,val in FOLDS:
        train=pd.concat([data[m] for m in training],ignore_index=True)
        valid=data[val]
        coverage.append({"fold":fold,"training_months":"+".join(map(str,training)),
                         "validation_month":val,"train_broader_n":len(train),
                         "train_headline_n":int(train.headline.sum()),
                         "valid_broader_n":len(valid),"valid_headline_n":int(valid.headline.sum()),
                         "valid_headline_pct_broader":100*valid.headline.mean()})
        for columns in [FEATURES,FEATURES+["SOG_kn","ME_TC_RPM_Transducer"]]:
            matching.extend(matched(train,valid,fold,columns))
        regimes.extend(clusters(train,valid,fold))
        print(f"completed {fold}",flush=True)
    m=pd.DataFrame(matching)
    m.to_csv(OUT/"fold_matched_shift_decomposition.csv",index=False)
    pd.DataFrame(regimes).to_csv(OUT/"fold_train_defined_regime_clusters.csv",index=False)
    pd.DataFrame(coverage).to_csv(OUT/"fold_scope_coverage.csv",index=False)
    select=m[(m.features=="+".join(FEATURES))&(m.caliper_train_iqr==.5)]
    fig,ax=plt.subplots(figsize=(8,4))
    x=np.arange(len(select))
    ax.bar(x-.17,select.composition_component_kw,.34,label="Feature-composition component")
    ax.bar(x+.17,select.conditional_component_kw,.34,label="Conditional target component")
    for i,row in enumerate(select.itertuples()):
        ax.text(i,-20,f"matched {row.matched_n:,}/{row.validation_headline_complete_n:,}",
                ha="center",va="top",fontsize=8)
    ax.axhline(0,color="0.4",lw=1)
    ax.set_xticks(x,select.fold.str.upper())
    ax.set(ylabel="Later minus earlier target mean (kW)",
           title="Train-only 4D neighbor decomposition; common support only")
    ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(OUT/"fold_matched_shift_decomposition.png",dpi=170)
    plt.close(fig)
    print(select[["fold","matched_n","matched_pct","composition_component_kw",
                  "conditional_component_kw"]].to_string(index=False),flush=True)


if __name__=="__main__":main()
