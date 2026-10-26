"""Classify sampled zero-run boundaries without treating speed thresholds as sensor recovery."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path("outputs/task3_v3/zero_states")
MECHANICAL=["SHAFT_MechPower_kW","SHAFT_Torque_Nm_TQ","SHAFT_RPM_TQ",
            "SHAFT_ThrustForce_kN_TQ"]
INDEPENDENT=["ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar","STW_kn"]


def main():
    changes=pd.read_csv(ROOT/"ten_minute_transitions.csv")
    raw=pd.read_csv(ROOT/"selected_raw_readings.csv.gz")
    rows=[];switch=[]
    for (episode,boundary),group in changes.groupby(["episode","boundary"]):
        by=group.set_index("channel")
        p0=by.loc["SHAFT_MechPower_kW","before_median"]
        p1=by.loc["SHAFT_MechPower_kW","after_median"]
        if p0>100 and p1==0:kind="observed mechanical-zero onset"
        elif p0==0 and p1>100:kind="observed mechanical recovery"
        elif p0==0 and p1==0:kind="speed-threshold boundary within zero state"
        else:kind="mixed or unresolved boundary"
        record={"episode":episode,"boundary":boundary,"classification":kind,
                "target_before_kw":p0,"target_after_kw":p1}
        for channel in MECHANICAL+INDEPENDENT:
            if channel in by.index:
                b=by.loc[channel,"before_median"];a=by.loc[channel,"after_median"]
                record[f"{channel}__before"]=b
                record[f"{channel}__after"]=a
                record[f"{channel}__pct_change"]=(100*(a-b)/abs(b) if abs(b)>1e-9 else np.nan)
        rows.append(record)
        if kind not in {"observed mechanical-zero onset","observed mechanical recovery"}:
            continue
        sample=raw[(raw.episode==episode)&(raw.boundary==boundary)
                   &raw.channel.isin(MECHANICAL)]
        for channel in MECHANICAL:
            d=sample[sample.channel==channel].sort_values("raw_timestamp")
            status=d.value.eq(0).to_numpy()
            change=np.flatnonzero(status[1:]!=status[:-1])+1
            if kind=="observed mechanical-zero onset":
                selected=[i for i in change if status[i]]
            else:selected=[i for i in change if not status[i]]
            if not selected:
                continue
            i=selected[0]
            switch.append({"episode":episode,"boundary":boundary,"classification":kind,
                           "channel":channel,"last_before_ts":d.raw_timestamp.iloc[i-1],
                           "last_before_value":d.value.iloc[i-1],
                           "first_after_ts":d.raw_timestamp.iloc[i],
                           "first_after_value":d.value.iloc[i],
                           "time_between_samples_s":(pd.Timestamp(d.raw_timestamp.iloc[i])-
                                                     pd.Timestamp(d.raw_timestamp.iloc[i-1])).total_seconds()})
    table=pd.DataFrame(rows)
    table.to_csv(ROOT/"boundary_classification.csv",index=False)
    events=pd.DataFrame(switch)
    events.to_csv(ROOT/"raw_mechanical_switch_events.csv",index=False)
    audit=pd.read_csv(ROOT/"torquemeter_minute_audit_2024.csv.gz")
    counter_cols=["SHAFT_Revolutions_TQ","SHAFT_MechEnergy_kWh_TQ"]
    mask=audit.zero_forward_active & (~audit.revolutions_frozen | ~audit.energy_frozen)
    exceptions=audit.loc[mask,["window_end_utc"]+counter_cols].copy()
    for col in counter_cols:
        exceptions[col+"__delta_from_previous_minute"]=(
            audit[col]-audit[col].shift(1)).loc[mask].to_numpy()
    exceptions.to_csv(ROOT/"counter_discontinuities.csv",index=False)
    print(table[["episode","boundary","classification","target_before_kw","target_after_kw",
                 "ME_RPM_CAMS__pct_change","ME_FuelLoad_pct__pct_change","STW_kn__pct_change"]].to_string(index=False))
    print(events[["episode","channel","last_before_ts","first_after_ts","time_between_samples_s"]].to_string(index=False))


if __name__=="__main__":main()
