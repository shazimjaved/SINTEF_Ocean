"""Information contracts, V7 transition evidence, separate raw mechanical identity."""
from __future__ import annotations

from v8_common import *
import sys
sys.path.insert(0,str(ROOT/"scripts"))
from channel_config import COLUMN_TO_QID


def specifications(dest):
    rows = [
        {"scenario":"A", "available":"independent onboard measurements from completed minute and earlier; frozen earlier training labels",
         "unavailable":"current/past target as a predictor; all torquemeter inputs; unverified Noon/provider timing",
         "prediction_time":"window end t; raw interval [t-1min,t)",
         "power_source":"ML estimate", "assumption":"onboard sensor latency within completed-minute contract; operational latency not verified",
         "limitation":"prior experiments show cross-period offsets and unidentifiable recorded shaft-zero states"},
        {"scenario":"B", "available":"A plus trusted past power with label timestamp < covered-day start minus 24h; daily refresh",
         "unavailable":"same-day/future labels or current shaft state truth",
         "prediction_time":"t; 3d history [day-4d,day-1d), effective label age approximately 24-48h",
         "power_source":"fixed Ridge plus delayed residual; delayed persistence/mean matched to history",
         "assumption":"CONDITIONAL: trustworthy labels and actual issuance latency unverified",
         "limitation":"a transition after cutoff may be invisible; historical-state flags cannot identify current state"},
        {"scenario":"C", "available":"power channel missing only; synchronous valid torque and shaft RPM still available",
         "unavailable":"independent verification of shared torquemeter calculation and N*m/kN*m convention",
         "prediction_time":"exact common raw timestamp; no nearest match, forward fill or future interpolation",
         "power_source":"DIAGNOSTIC ONLY: P[kW]=2*pi*T[Nm]*rpm/60000; if numeric T is kNm multiply this by 1000",
         "assumption":"torque/RPM available and trustworthy at that timestamp; measurement/package status known",
         "limitation":"same registered Instrument Torquemeter source; apparent numerical identity is not independent validation or a primary ML baseline"},
        {"scenario":"D", "available":"independent onboard features and any legally delayed power labels",
         "unavailable":"usable contemporaneous torque/RPM when entire package unavailable; true shaft state during coordinated zeros",
         "prediction_time":"completed-minute end; missing and explicitly recorded zero remain distinct",
         "power_source":"A/B conditional estimate or abstention; formula cannot add independent information when all trio channels are absent/zero",
         "assumption":"requires status/quality, clutch/propulsion configuration and independent shaft measurement to resolve state",
         "limitation":"never relabel observed zeros as missing/faulty automatically"},
    ]
    WRITE(pd.DataFrame(rows),dest/"information_availability.csv")


def transition_cases(dest):
    blocks=pd.read_csv(OLD/"reconstruction_blocks.csv")
    detail=[]; daily=[]; summaries=[]
    for month in [6,8,9]:
        h=load_v7_history(month)
        baseline=json.loads((OLD/f"reconstruction/baselines_m{month:02d}.json").read_text())
        stats,ledger=history_stats(h,h,baseline["mean_kw"])
        source=LOAD(month)
        hide=V7["hidden_mask"](source,blocks)
        allowed_any=source.loc[OBSERVED(source) & ~hide].copy()
        allowed_any["_ts"]=TS(allowed_any)
        for case in [name for name in CASES if name.startswith(f"m{month:02d}")]:
            original=pd.read_csv(OLD/f"reconstruction/predictions_{case}.csv.gz",
                                 dtype={"fixed__B_ridge_full":"float32"})
            s=stats[stats.window_end_utc.isin(original.window_end_utc)].copy()
            assert s.window_end_utc.tolist()==original.window_end_utc.tolist()
            assert np.allclose(s.v7_calibrated,original.calibrated__B_ridge_full,atol=1e-6)
            s["actual_kw"]=original.actual_kw.to_numpy()
            for col in ["observed_truth","positive","recorded_zero","negative_or_mixed"]:
                s[col]=original[col].to_numpy()
            s["case_id"]=case
            s["v7_prediction_sha256"]=DIGEST(OLD/f"reconstruction/predictions_{case}.csv.gz")
            for day,p in s.groupby("prediction_day_utc"):
                r=p.iloc[0]
                cutoff=pd.Timestamp(r.history_cutoff_exclusive_utc)
                pool=allowed_any[allowed_any._ts.lt(cutoff)].sort_values("_ts")
                last=pool.iloc[-1] if len(pool) else None
                sel=s.prediction_day_utc.eq(day)
                s.loc[sel,"last_available_any_scope_label_utc"]=last.window_end_utc if last is not None else ""
                s.loc[sel,"last_available_any_scope_power_kw"]=float(last[TARGET]) if last is not None else np.nan
                record={"case_id":case,"prediction_day_utc":day,
                        "history_cutoff_exclusive_utc":r.history_cutoff_exclusive_utc,
                        "last_admitted_label_utc":r.last_admitted_label_utc,
                        "last_available_any_scope_label_utc":last.window_end_utc if last is not None else "",
                        "last_available_any_scope_power_kw":float(last[TARGET]) if last is not None else np.nan,
                        "history_n":r.history_n,"zero_fraction":r.zero_fraction,
                        "positive_fraction":r.positive_fraction,"negative_fraction":r.negative_fraction,
                        "residual_offset_kw":r.offset_kw,"history_residual_mad_kw":r.residual_mad_kw,
                        "first_prediction_utc":p.window_end_utc.iloc[0],"last_prediction_utc":p.window_end_utc.iloc[-1],
                        "median_label_age_hours":p.label_age_hours.median(),
                        "median_correction_age_hours":p.correction_age_hours.median(),
                        "scored_forward_n":int((p.operational_eligible&p.observed_truth).sum())}
                for col in FEATURES:
                    record[f"current_median__{col}"]=float(p[col].median())
                    record[f"history_median__{col}"]=r[f"history_median__{col}"]
                daily.append(record)
            for method in ["fixed_ridge","v7_calibrated","delayed_persistence","delayed_history_mean"]:
                select=s.operational_eligible&s.observed_truth
                summaries.append({"case_id":case,"method":method,
                                  "recorded_zero_n":int((select&s.recorded_zero).sum()),
                                  "positive_n":int((select&s.positive).sum()),
                                  **METRIC(s.loc[select,"actual_kw"],s.loc[select,method])})
            detail.append(s)
    WRITE(pd.concat(detail,ignore_index=True),dest/"transition_case_minutes.csv.gz")
    WRITE(pd.DataFrame(daily),dest/"transition_case_daily_information.csv")
    WRITE(pd.DataFrame(summaries),dest/"transition_case_metrics.csv")


def mechanical_identity(dest):
    names=[TARGET,"SHAFT_Torque_Nm_TQ","SHAFT_RPM_TQ"]
    mapping={COLUMN_TO_QID[c]:c for c in names}
    selected=[]; summaries=[]; aggregate=[]
    # Representative diagnostic windows only; complete monthly selected-channel
    # pivots stay bounded (three QIDs, one month) and are immediately released.
    windows={6:[("2024-06-12T05:55Z","2024-06-12T06:10Z"),
                ("2024-06-18T05:55Z","2024-06-18T06:10Z"),
                ("2024-06-18T14:48Z","2024-06-18T15:00Z")],
             8:[("2024-08-27T19:55Z","2024-08-27T20:10Z")],
             9:[("2024-09-10T04:20Z","2024-09-10T04:35Z"),
                ("2024-09-12T05:55Z","2024-09-12T06:10Z")]}
    for month in windows:
        chunks=[]
        for chunk in pd.read_csv(ROOT/f"data/raw/{month}.csv",header=None,
                                 names=["raw_timestamp","qid","value"],
                                 dtype={"raw_timestamp":"str","qid":"str","value":"float64"},chunksize=100000):
            keep=chunk[chunk.qid.isin(mapping)]
            if len(keep):chunks.append(keep)
        data=pd.concat(chunks,ignore_index=True)
        duplicate_n=int(data.duplicated(["raw_timestamp","qid"]).sum())
        assert duplicate_n==0,"Raw trio duplicates require explicit resolution"
        data["channel"]=data.qid.map(mapping)
        trio=data.pivot(index="raw_timestamp",columns="channel",values="value").sort_index()
        t=pd.to_datetime(trio.index,utc=True)
        available=trio[names].notna()
        complete=available.all(axis=1)
        positive=complete & trio[TARGET].gt(100) & trio[names[1]].gt(1) & trio[names[2]].gt(10)
        formula_knm=2*np.pi/60*trio[names[1]]*trio[names[2]]
        formula_nm=formula_knm/1000
        factor=trio.loc[positive,TARGET]/(trio.loc[positive,names[1]]*trio.loc[positive,names[2]])
        absolute_error=(trio.loc[positive,TARGET]-formula_knm[positive]).abs()
        zeros=complete & trio[TARGET].eq(0)
        summaries.append({"month":month,"union_three_qid_timestamps":len(trio),"duplicate_timestamp_qid_n":duplicate_n,
                          "exact_coobserved_triplets":int(complete.sum()),
                          "power_missing_torque_rpm_present":int((~available[TARGET]&available[names[1]]&available[names[2]]).sum()),
                          "power_present_torque_or_rpm_missing":int((available[TARGET]&~(available[names[1]]&available[names[2]])).sum()),
                          "positive_triplets":int(positive.sum()),"observed_factor_median":float(factor.median()),
                          "ratio_to_literal_Nm_factor":float(factor.median()/(2*np.pi/60000)),
                          "formula_MAE_kw_if_numeric_kNm":float(absolute_error.mean()),
                          "formula_median_absolute_error_kw":float(absolute_error.median()),
                          "formula_p95_absolute_error_kw":float(absolute_error.quantile(.95)),
                          "formula_p99_absolute_error_kw":float(absolute_error.quantile(.99)),
                          "formula_max_absolute_error_kw":float(absolute_error.max()),
                          "positive_fraction_within_1kw":float(absolute_error.le(1).mean()),
                          "formula_MAE_kw_if_literal_Nm":float((trio.loc[positive,TARGET]-formula_nm[positive]).abs().mean()),
                          "power_zero_triplets":int(zeros.sum()),
                          "power_zero_torque_rpm_both_zero_n":int((zeros & trio[names[1]].eq(0)&trio[names[2]].eq(0)).sum()),
                          "power_zero_torque_rpm_both_nonzero_n":int((zeros & trio[names[1]].ne(0)&trio[names[2]].ne(0)).sum())})
        select=np.zeros(len(trio),bool)
        for start,end in windows[month]:
            select|=(t>=pd.Timestamp(start))&(t<pd.Timestamp(end))
        sample=trio.loc[select].reset_index()
        sample["month"]=month
        sample["formula_kw_if_numeric_kNm"]=formula_knm.loc[select].to_numpy()
        sample["formula_kw_if_literal_Nm"]=formula_nm.loc[select].to_numpy()
        selected.append(sample)
        rawtime=pd.to_datetime(sample.raw_timestamp,utc=True)
        sample["window_end_utc"]=(rawtime.dt.floor("min")+pd.Timedelta(minutes=1)).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        g=sample.groupby("window_end_utc").agg(raw_power_mean=(TARGET,"mean"),raw_n=(TARGET,"count"),
                torque_mean=(names[1],"mean"),shaft_rpm_mean=(names[2],"mean"),
                mean_of_aligned_product_kw=("formula_kw_if_numeric_kNm","mean")).reset_index()
        g["product_of_means_kw"]=2*np.pi/60*g.torque_mean*g.shaft_rpm_mean
        d=LOAD(month)
        g=g.merge(d[["window_end_utc",TARGET,"target_n"]],on="window_end_utc",validate="one_to_one")
        # Only fully sampled source minutes permit a raw-to-minute mean check.
        g["complete_source_minute"]=g.raw_n.eq(g.target_n)
        g["raw_to_compact_difference_kw"]=g.raw_power_mean-g[TARGET]
        g["month"]=month
        aggregate.append(g)
        print("raw mechanical identity audited month",month,flush=True)
    WRITE(pd.DataFrame(summaries),dest/"raw_mechanical_identity_summary.csv")
    WRITE(pd.concat(selected,ignore_index=True),dest/"raw_synchronous_triplets.csv.gz")
    WRITE(pd.concat(aggregate,ignore_index=True),dest/"raw_to_minute_alignment.csv")
    dictionary=pd.read_csv(ROOT/"outputs/tables/data_dictionary.csv")
    WRITE(dictionary[dictionary.qid.isin(mapping)][["qid","quantity_name","source_name","unit"]],dest/"registered_mechanical_channels.csv")


def main():
    prepare(); dest=OUT/"audit";dest.mkdir(exist_ok=True)
    if (dest/"completed.json").exists():
        print("PASS: existing V8 source/information audit preserved");return
    specifications(dest);transition_cases(dest);mechanical_identity(dest)
    (dest/"completed.json").write_text(json.dumps({"completed":True,"raw_months":[6,8,9],
        "primary_model_use_of_torque_rpm":False,"V7_window_comment":"documentation typo; actual preprocessing uses [end-1min,end)"},indent=2))
    print("PASS: information contracts, four transition cases and source-level physics diagnostics saved")


if __name__=="__main__":main()
