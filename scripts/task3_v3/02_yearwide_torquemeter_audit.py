"""Chunked year-wide QID audit of synchronous torquemeter zero states.

The torquemeter readings are diagnostic source signals, never model inputs.
This streams one monthly long CSV at a time and keeps only minute arrays.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_config import COLUMN_TO_QID

RAW = Path("data/raw")
DATA = Path("outputs/task3/data")
OUT = Path("outputs/task3_v3/zero_states")
TARGET = "SHAFT_MechPower_kW"
CHANNELS = [TARGET, "SHAFT_RPM_TQ", "SHAFT_Torque_Nm_TQ",
            "SHAFT_Revolutions_TQ", "SHAFT_MechEnergy_kWh_TQ",
            "SHAFT_ThrustForce_kN_TQ", "ME_FuelMassFlow_kghr_TQ"]
QID_TO_INDEX = {COLUMN_TO_QID[col]: i for i, col in enumerate(CHANNELS)}


def aggregate(month):
    start = pd.Timestamp(2024, month, 1, tz="UTC")
    stop = start + pd.offsets.MonthBegin(1)
    n = int((stop-start).total_seconds()/60)
    sums = np.zeros((len(CHANNELS), n), dtype=np.float64)
    counts = np.zeros((len(CHANNELS), n), dtype=np.int16)
    for chunk in pd.read_csv(RAW / f"{month}.csv", header=None,
                             names=["ts", "qid", "value"], chunksize=300_000,
                             dtype={"ts":"string", "qid":"string", "value":"float64"}):
        sub = chunk[chunk.qid.isin(QID_TO_INDEX)]
        if sub.empty:
            continue
        ts = pd.to_datetime(sub.ts, utc=True, errors="raise")
        minute = ((pd.DatetimeIndex(ts).as_unit("ns").asi8-start.value)//60_000_000_000).astype(np.int32)
        if ((minute<0)|(minute>=n)).any():
            raise ValueError(f"Torquemeter row outside source month {month}")
        q = sub.qid.map(QID_TO_INDEX).to_numpy(dtype=np.int8)
        v = sub.value.to_numpy(dtype=np.float64)
        if not np.isfinite(v).all():
            raise ValueError("Nonfinite torquemeter reading")
        np.add.at(sums, (q, minute), v)
        np.add.at(counts, (q, minute), 1)
    values = np.divide(sums, counts, out=np.full_like(sums,np.nan), where=counts>0)
    feature_cols=["window_end_utc",TARGET,"target_n","STW_kn","ME_RPM_CAMS",
                  "ME_FuelLoad_pct","ME_ScavAirPressure_bar"]
    feature=pd.read_csv(DATA/f"minute_2024_{month:02d}.csv.gz", usecols=feature_cols)
    if len(feature)!=n:
        raise ValueError("Feature minute-grid length mismatch")
    reference=feature[TARGET].to_numpy(dtype=np.float64)
    observed=counts[0]>0
    if not np.array_equal(counts[0].astype(np.int64),feature.target_n.to_numpy(dtype=np.int64)):
        raise ValueError(f"Target raw count mismatch in month {month}")
    if not np.allclose(values[0,observed],reference[observed],atol=.02,rtol=2e-6):
        raise ValueError(f"Target raw mean mismatch in month {month}")
    frame=feature[["window_end_utc"]].copy()
    frame["source_month"]=month
    for i,col in enumerate(CHANNELS):
        frame[col]=values[i].astype(np.float64)
        frame["n__"+col]=counts[i]
    for col in ["STW_kn","ME_RPM_CAMS","ME_FuelLoad_pct","ME_ScavAirPressure_bar"]:
        frame[col]=feature[col].to_numpy(dtype=np.float32)
    frame["zero_forward_active"]=(observed & np.equal(values[0],0)
        & frame.STW_kn.ge(3).to_numpy()
        & frame.ME_RPM_CAMS.gt(50).to_numpy()
        & frame.ME_FuelLoad_pct.gt(20).to_numpy()
        & frame.ME_ScavAirPressure_bar.gt(.5).to_numpy())
    frame["torque_zero"]=(counts[2]>0)&np.equal(values[2],0)
    frame["shaft_rpm_zero"]=(counts[1]>0)&np.equal(values[1],0)
    frame["thrust_zero"]=(counts[5]>0)&np.equal(values[5],0)
    # Counter stasis requires observations in the current and previous minute.
    # The first minute of each month is left unknown here; yearwide continuity
    # is assessed after all monthly frames are concatenated.
    return frame


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    parts=[]
    for month in range(1,13):
        frame=aggregate(month)
        parts.append(frame)
        print(f"raw month {month:02d}: {int(frame.zero_forward_active.sum())} active-engine zero minutes",flush=True)
    year=pd.concat(parts,ignore_index=True)
    assert len(year)==527040 and year.window_end_utc.is_unique
    for col,name in [("SHAFT_Revolutions_TQ","revolutions_frozen"),
                     ("SHAFT_MechEnergy_kWh_TQ","energy_frozen")]:
        current=year[col].to_numpy(dtype=np.float64)
        prev=np.roll(current,1);prev[0]=np.nan
        year[name]=np.isfinite(current)&np.isfinite(prev)&np.isclose(current,prev,atol=1e-5,rtol=0)
    cols=["window_end_utc","source_month","zero_forward_active","torque_zero",
          "shaft_rpm_zero","thrust_zero","revolutions_frozen","energy_frozen",
          TARGET,"SHAFT_RPM_TQ","SHAFT_Torque_Nm_TQ","SHAFT_Revolutions_TQ",
          "SHAFT_MechEnergy_kWh_TQ","ME_RPM_CAMS","ME_FuelLoad_pct","STW_kn"]
    year[cols].to_csv(OUT/"torquemeter_minute_audit_2024.csv.gz",index=False,compression="gzip")
    rows=[]
    for month,frame in year.groupby("source_month"):
        z=frame.zero_forward_active
        good=z & frame.torque_zero & frame.shaft_rpm_zero & frame.thrust_zero
        counter=good & frame.revolutions_frozen & frame.energy_frozen
        rows.append({"month":month,"zero_forward_active_min":int(z.sum()),
                     "all_power_torque_rpm_thrust_zero_min":int(good.sum()),
                     "all_zero_and_both_counters_frozen_min":int(counter.sum()),
                     "torque_missing_in_zero_min":int((z & frame.SHAFT_Torque_Nm_TQ.isna()).sum()),
                     "rpm_missing_in_zero_min":int((z & frame.SHAFT_RPM_TQ.isna()).sum()),
                     "positive_target_zero_shaft_rpm_min":int(((frame[TARGET]>0)&frame.shaft_rpm_zero).sum())})
    result=pd.DataFrame(rows)
    result.to_csv(OUT/"yearwide_torquemeter_zero_summary.csv",index=False)
    print(result.to_string(index=False),flush=True)


if __name__=="__main__":
    main()
