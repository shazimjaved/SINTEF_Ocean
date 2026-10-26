"""Plot saved development-only fold metrics; no fitting or December input."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path("outputs/task3_v3/models")
NAMES=["B_ridge_recent90","B_derived_ridge_recent90",
       "B_dynamic_ridge_recent90","B_dynamic_hgb_recent90"]
LABEL={
    "B_ridge_recent90":"V2 Ridge recent 90",
    "B_derived_ridge_recent90":"V3 Ridge + onboard ratios",
    "B_dynamic_ridge_recent90":"V3 Ridge + trailing history",
    "B_dynamic_hgb_recent90":"V3 HGB + trailing history",
}


def main():
    data=pd.read_csv(ROOT/"v3_development_with_v2_baselines.csv")
    data=data[data.candidate.isin(NAMES)]
    assert len(data)==len(NAMES)*4*2
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
    folds=["apr","may","jun","aug"]
    for column,scope in enumerate(["headline","broader_forward"]):
        scoped=data[data.scope==scope]
        for name in NAMES:
            d=scoped[scoped.candidate==name].set_index("fold").loc[folds]
            axes[0,column].plot(range(4),d.mae_kw,marker="o",linewidth=1.8,label=LABEL[name])
            axes[1,column].plot(range(4),d.r2_score,marker="o",linewidth=1.8)
        n=scoped[scoped.candidate==NAMES[0]].set_index("fold").loc[folds].n
        for i,count in enumerate(n):
            axes[0,column].annotate(f"n={count:,}",(i,0),xycoords=("data","axes fraction"),
                                    xytext=(0,5),textcoords="offset points",ha="center",fontsize=7)
        axes[0,column].set_title(scope.replace("_"," ").title())
        axes[1,column].axhline(0,color="0.35",linewidth=1)
        axes[1,column].set_xticks(range(4),[x.upper() for x in folds])
        for row in range(2):axes[row,column].grid(alpha=.2)
    axes[0,0].set_ylabel("MAE (kW)")
    axes[1,0].set_ylabel("R² (sklearn)")
    axes[1,0].set_xlabel("Chronological validation month")
    axes[1,1].set_xlabel("Chronological validation month")
    axes[0,0].legend(fontsize=7,ncol=2,loc="upper left")
    fig.suptitle("Label-free onboard experiments; separate label scopes; no December tuning",fontsize=11)
    fig.tight_layout();fig.savefig(ROOT/"v3_label_free_fold_metrics.png",dpi=170)
    plt.close(fig)


if __name__=="__main__":main()
