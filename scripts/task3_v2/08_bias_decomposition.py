"""Separate bias from residual variation in development fold errors.

The 'oracle offset' column is a retrospective mathematical bound using the
validation labels. It is NOT a fitted, deployable or selected model.
"""
import runpy
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT=Path("outputs/task3_v2/experiments")
CODE=runpy.run_path("scripts/task3_v2/07_walkforward_experiments.py")
load,mask=CODE["load"],CODE["mask"]


def main():
    result=pd.read_csv(OUT/"v2_walkforward_results.csv")
    head=result[result.scope=="headline"].copy()
    variances={}
    for name,_,month in CODE["FOLDS"]:
        frame=load(month)
        y=frame.loc[mask(frame),CODE["TARGET"]].to_numpy(dtype=np.float64)
        variances[name]=float(np.var(y,ddof=0))
    head["target_variance_kw2"]=head.fold.map(variances)
    head["mse_kw2"]=np.square(head.rmse_kw)
    head["squared_bias_kw2"]=np.square(head.bias_kw)
    head["residual_variance_kw2"]=(head.mse_kw2-head.squared_bias_kw2).clip(lower=0)
    head["bias_pct_mse"]=100*head.squared_bias_kw2/head.mse_kw2
    head["oracle_centered_r2"] = 1-head.residual_variance_kw2/head.target_variance_kw2
    head["mae_minus_abs_bias_kw"]=head.mae_kw-head.bias_kw.abs()
    head.to_csv(OUT/"v2_bias_decomposition.csv",index=False)
    fig,axes=plt.subplots(1,2,figsize=(10,4.2))
    august=head[head.fold=="aug"]
    axes[0].scatter(august.pearson_r,august.r2_score,s=55)
    for row in august.itertuples():
        axes[0].annotate(row.candidate.replace("_"," "),(row.pearson_r,row.r2_score),
                         xytext=(3,3),textcoords="offset points",fontsize=6)
    axes[0].set(xlabel="August Pearson r",ylabel="August R²",
                title="High association can coexist with negative R²")
    bars=axes[1].bar(august.candidate,august.bias_pct_mse,color="#2a788e")
    axes[1].tick_params(axis="x",rotation=70,labelsize=7)
    axes[1].set(ylabel="Squared bias / MSE (%)",title="August error decomposition")
    fig.tight_layout()
    fig.savefig(OUT/"v2_august_bias_decomposition.png",dpi=180)
    plt.close(fig)
    print(august[["candidate","mae_kw","bias_kw","bias_pct_mse",
                  "pearson_r","r2_score","oracle_centered_r2"]].round(3).to_string(index=False))


if __name__=="__main__":
    main()
