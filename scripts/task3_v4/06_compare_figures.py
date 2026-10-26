"""Figures from saved V4 development results; no fitting or December input."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path("outputs/task3_v4")
FOLDS=["apr","may","jun","aug"]
FAMILIES=["B_ridge_head","B_hgb_head","B_xgb_head","B_lgbm_head","B_cat_head"]
ABLATION=["A_lgbm_head","B_lgbm_head","D_lgbm_head"]
LABEL={"B_ridge_head":"Ridge","B_hgb_head":"HGB","B_xgb_head":"XGBoost",
       "B_lgbm_head":"LightGBM","B_cat_head":"CatBoost",
       "A_lgbm_head":"Restricted onboard","D_lgbm_head":"Onboard + derived/history"}


def plot_comparison(data,names,title,destination):
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
    for col,scope in enumerate(["headline","broader_forward"]):
        subset=data[data.scope==scope]
        for name in names:
            d=subset[subset.candidate==name].set_index("fold").loc[FOLDS]
            axes[0,col].plot(range(4),d.mae_kw,marker="o",linewidth=1.8,label=LABEL.get(name,name))
            axes[1,col].plot(range(4),d.r2_score,marker="o",linewidth=1.8)
        counts=subset[subset.candidate==names[0]].set_index("fold").loc[FOLDS].n
        for x,n in enumerate(counts):
            axes[0,col].annotate(f"n={n:,}",(x,0),xycoords=("data","axes fraction"),
                                 xytext=(0,4),textcoords="offset points",ha="center",fontsize=7)
        axes[0,col].set_title(scope.replace("_"," ").title())
        axes[1,col].axhline(0,color="0.4",linewidth=1)
        axes[1,col].set_xticks(range(4),[f.upper() for f in FOLDS])
        for row in range(2):axes[row,col].grid(alpha=.2)
    axes[0,0].set_ylabel("MAE (kW)")
    axes[1,0].set_ylabel("R² (sklearn)")
    axes[1,0].set_xlabel("Chronological validation month")
    axes[1,1].set_xlabel("Chronological validation month")
    axes[0,0].legend(fontsize=7,ncol=2)
    fig.suptitle(title,fontsize=11)
    fig.tight_layout();fig.savefig(destination,dpi=170);plt.close(fig)


def main():
    d=pd.read_csv(ROOT/"models/v4_boosting_development.csv")
    assert len(d)==15*4*2
    plot_comparison(d,FAMILIES,"Same onboard inputs across five model families; no December",
                    ROOT/"models/v4_family_comparison.png")
    plot_comparison(d,ABLATION,"LightGBM onboard feature ablation; no December",
                    ROOT/"models/v4_feature_ablation.png")
    s=pd.read_csv(ROOT/"state/august_state_identifiability.csv")
    o=pd.read_csv(ROOT/"state/same_month_zero_positive_overlap.csv")
    fig,axes=plt.subplots(1,2,figsize=(9,3.8))
    axes[0].bar(s.feature_set,s.roc_auc,color="#4267a3")
    axes[0].axhline(.5,color="0.4",linestyle="--")
    axes[0].set(ylabel="August ROC AUC",title="Recorded-zero state identifiability")
    axes[0].tick_params(axis="x",rotation=20)
    for month,d2 in o.groupby("month"):
        axes[1].plot(d2.caliper_train_iqr,d2.overlap_pct,marker="o",label=f"Month {month}")
    axes[1].set(xlabel="5th-neighbor distance caliper (train IQR)",
                ylabel="Zero minutes with 5 positive analogs (%)",
                title="Same-month independent-feature overlap")
    axes[1].legend()
    fig.tight_layout();fig.savefig(ROOT/"state/v4_state_identifiability.png",dpi=170)
    plt.close(fig)
    assisted_path=ROOT/"label_assisted/label_assisted_development.csv"
    if assisted_path.exists():
        a=pd.read_csv(assisted_path)
        subset=a[(a.candidate=="B_ridge_head")&(a.scope=="headline")]
        fig,ax=plt.subplots(figsize=(8,4))
        for name,d2 in subset.groupby("scenario"):
            ax.plot(range(4),d2.set_index("fold").loc[FOLDS].mae_kw,
                    marker="o",label=name.replace("_"," "))
        ax.set_xticks(range(4),[f.upper() for f in FOLDS])
        ax.set(ylabel="Headline MAE (kW)",xlabel="Validation month",
               title="Conditional delayed-label scenario (different information)")
        ax.legend();ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(ROOT/"label_assisted/delayed_label_scenario.png",dpi=170)
        plt.close(fig)


if __name__=="__main__":main()
