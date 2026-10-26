"""Summarize both label scopes from saved development metrics; no fitting."""
from pathlib import Path

import pandas as pd

ROOT=Path("outputs/task3_v4/models")


def main():
    data=pd.read_csv(ROOT/"v4_boosting_development.csv")
    if len(data)!=15*4*2:raise ValueError("Incomplete fixed comparison")
    rows=[]
    for (candidate,scope),d in data.groupby(["candidate","scope"]):
        aug=d[d.fold=="aug"].iloc[0]
        jun=d[d.fold=="jun"].iloc[0]
        rows.append({"candidate":candidate,"scope":scope,
                     "mean_fold_mae_kw":d.mae_kw.mean(),
                     "worst_fold_mae_kw":d.mae_kw.max(),
                     "negative_r2_folds":int(d.r2_score.lt(0).sum()),
                     "min_fold_r2":d.r2_score.min(),
                     "august_n":aug.n,"august_mae_kw":aug.mae_kw,
                     "august_rmse_kw":aug.rmse_kw,"august_r2":aug.r2_score,
                     "august_pearson_r":aug.pearson_r,"august_bias_kw":aug.bias_kw,
                     "june_n":jun.n,"june_mae_kw":jun.mae_kw,
                     "june_r2":jun.r2_score})
    out=pd.DataFrame(rows).sort_values(["scope","worst_fold_mae_kw"])
    out.to_csv(ROOT/"v4_scope_stability.csv",index=False)
    print(out[["candidate","scope","negative_r2_folds","august_mae_kw",
               "august_r2","june_mae_kw","june_r2"]].to_string(index=False))


if __name__=="__main__":main()
