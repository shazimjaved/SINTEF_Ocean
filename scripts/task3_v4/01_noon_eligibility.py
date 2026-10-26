"""Audit Noon Report loading fields without joining them into model minutes.

Date-only rows do not establish measurement or publication time. The tables
below are retrospective diagnostics and are never used as prediction inputs.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SOURCE=Path("data/Noon Reports")
OUT=Path("outputs/task3_v4/noon")
LOADING=["Fwd Draft","Mid Draft","Aft Draft","Displacement"]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=sorted(SOURCE.glob("*.csv"))
    if len(files)!=12:raise ValueError("Expected twelve monthly Noon files")
    all_rows=[];schema=[]
    for file in files:
        d=pd.read_csv(file,low_memory=False)
        dates=pd.to_datetime(d.Date,format="%d/%m/%Y",errors="raise")
        if dates.isna().any():raise ValueError(f"Missing date in {file}")
        time_cols=[c for c in d if any(term in c.lower() for term in
                   ["timestamp","issue","publish","report time","measurement time","recorded at"])]
        schema.append({"file":file.name,"rows":len(d),"columns":len(d.columns),
                       "date_only":dates.dt.strftime("%H:%M:%S").eq("00:00:00").all(),
                       "time_or_issue_columns":"|".join(time_cols),
                       "fwd_draft_present":int(d["Fwd Draft"].notna().sum()),
                       "mid_draft_present":int(d["Mid Draft"].notna().sum()),
                       "aft_draft_present":int(d["Aft Draft"].notna().sum()),
                       "displacement_present":int(d.Displacement.notna().sum())})
        d["source_file"]=file.name;d["parsed_date"]=dates
        all_rows.append(d)
    full=pd.concat(all_rows,ignore_index=True).sort_values("parsed_date")
    assert len(full)==366 and full.parsed_date.is_unique
    rows=[]
    for month,d in full.groupby(full.parsed_date.dt.month):
        row={"month":month,"days":len(d)}
        for col in LOADING:
            x=pd.to_numeric(d[col],errors="coerce")
            row[col.replace(" ","_").lower()+"_observed_days"]=int(x.notna().sum())
            row[col.replace(" ","_").lower()+"_distinct_values"]=int(x.nunique(dropna=True))
            row[col.replace(" ","_").lower()+"_median"]=float(x.median())
            row[col.replace(" ","_").lower()+"_p10"]=float(x.quantile(.1))
            row[col.replace(" ","_").lower()+"_p90"]=float(x.quantile(.9))
        rows.append(row)
    summary=pd.DataFrame(rows)
    pd.DataFrame(schema).to_csv(OUT/"noon_schema_and_timing.csv",index=False)
    summary.to_csv(OUT/"noon_loading_monthly_descriptive.csv",index=False)
    eligibility=pd.DataFrame([
        {"field_group":"same-day loading/draft","date_present":True,
         "measurement_time_present":False,"publication_time_present":False,
         "ranked_model_status":"excluded: timing not established"},
        {"field_group":"prior-day loading/draft","date_present":True,
         "measurement_time_present":False,"publication_time_present":False,
         "ranked_model_status":"excluded: report availability deadline not established"},
        {"field_group":"daily slip/consumption","date_present":True,
         "measurement_time_present":False,"publication_time_present":False,
         "ranked_model_status":"excluded: post-interval derivation and timing unverified"},
    ])
    eligibility.to_csv(OUT/"noon_feature_eligibility.csv",index=False)
    fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
    for i,col in enumerate(["displacement_median","mid_draft_median"]):
        axes[i].plot(summary.month,summary[col],marker="o")
        axes[i].set_ylabel("Daily median displacement" if i==0 else "Daily median mid draft")
        axes[i].grid(alpha=.25)
    axes[0].set_title("Retrospective Noon loading context; issue time unavailable")
    axes[1].set_xticks(range(1,13));axes[1].set_xlabel("2024 month")
    fig.tight_layout();fig.savefig(OUT/"noon_loading_monthly_descriptive.png",dpi=170)
    plt.close(fig)
    print(summary[["month","days","displacement_median","mid_draft_median"]].to_string(index=False))
    print({"files":len(files),"dates":len(full),"time_columns":sum(bool(x["time_or_issue_columns"]) for x in schema)})


if __name__=="__main__":main()
