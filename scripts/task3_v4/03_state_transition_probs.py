"""Summarize saved August classifier probabilities around the raw zero onset."""
from pathlib import Path

import pandas as pd

ROOT=Path("outputs/task3_v4/state")
ONSET=pd.Timestamp("2024-08-27T20:03:00Z")


def main():
    p=pd.read_csv(ROOT/"august_state_probabilities.csv.gz")
    p["ts"]=pd.to_datetime(p.window_end_utc,utc=True)
    rows=[]
    for name,d in p.groupby("feature_set"):
        for phase,start,end in [("before10",ONSET-pd.Timedelta(minutes=10),ONSET),
                                ("after10",ONSET,ONSET+pd.Timedelta(minutes=10)),
                                ("after24h",ONSET,ONSET+pd.Timedelta(days=1))]:
            selected=d[(d.ts>=start)&(d.ts<end)]
            rows.append({"feature_set":name,"phase":phase,"n":len(selected),
                         "observed_zero_n":int(selected.recorded_zero_state.sum()),
                         "probability_median":float(selected.predicted_zero_probability.median()),
                         "probability_mean":float(selected.predicted_zero_probability.mean()),
                         "probability_above_05_n":int(selected.predicted_zero_probability.ge(.5).sum())})
    out=pd.DataFrame(rows)
    out.to_csv(ROOT/"august_onset_probability_summary.csv",index=False)
    print(out.to_string(index=False))


if __name__=="__main__":main()
