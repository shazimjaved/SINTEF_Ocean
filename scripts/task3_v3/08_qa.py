"""Executable integrity checks for the V3 raw diagnostics and development folds."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path("outputs/task3_v3")
ROWS=[]


def check(identifier,claim,passed,evidence):
    ROWS.append({"id":identifier,"claim":claim,"status":"PASS" if passed else "FAIL",
                 "evidence":str(evidence)})


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda:file.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def main():
    original=json.loads(Path("outputs/task3/tables/frozen_artifact_sha256.json").read_text())
    check("V3Q01","V1 frozen model, selection and original December predictions remain unchanged",
          all(digest(path)==value for path,value in original.items()),f"{len(original)} hashes")
    zero=pd.read_csv(ROOT/"zero_states/torquemeter_minute_audit_2024.csv.gz")
    check("V3Q02","Year-wide torquemeter audit covers unique completed minutes",
          len(zero)==527040 and zero.window_end_utc.is_unique and zero.source_month.nunique()==12,
          f"{len(zero)} minutes")
    z=zero[zero.zero_forward_active]
    simultaneous=(z.torque_zero&z.shaft_rpm_zero&z.thrust_zero).sum()
    frozen=(z.torque_zero&z.shaft_rpm_zero&z.thrust_zero&
            z.revolutions_frozen&z.energy_frozen).sum()
    check("V3Q03","Active-engine zero-power minutes have synchronous mechanical torquemeter zeros",
          len(z)==38990 and simultaneous==len(z),f"{simultaneous}/{len(z)}")
    check("V3Q04","Counter stasis exceptions remain visible and are not called clean boundaries",
          frozen==38985 and len(z[~(z.revolutions_frozen&z.energy_frozen)])==5
          and ((z.window_end_utc=="2024-08-27T20:22:00Z")&~z.revolutions_frozen).any(),
          f"frozen={frozen}; discontinuities={len(z)-frozen}")
    switch=pd.read_csv(ROOT/"zero_states/raw_mechanical_switch_events.csv")
    groups=switch.groupby(["episode","boundary"])
    sync=all(len(g)==4 and g.first_after_ts.nunique()==1 and
             g.time_between_samples_s.max()<15.1 for _,g in groups)
    check("V3Q05","Sampled actual zero onsets and recovery switch four mechanical channels together",
          sync and len(groups)==4,f"events={len(groups)}; channels={len(switch)}")
    boundaries=pd.read_csv(ROOT/"zero_states/boundary_classification.csv")
    counts=boundaries.classification.value_counts().to_dict()
    check("V3Q06","Speed-threshold exits are separated from actual measurement recovery",
          counts.get("observed mechanical-zero onset")==3
          and counts.get("observed mechanical recovery")==1
          and counts.get("speed-threshold boundary within zero state")==4,counts)
    identity=pd.read_csv(ROOT/"zero_states/monthly_power_torque_identity.csv")
    expected=2*np.pi/60
    check("V3Q07","Positive-power conversion factor is stable and 1000x literal N-m factor",
          len(identity)==12 and np.allclose(identity.observed_factor_median,expected,rtol=.001)
          and identity.ratio_to_literal_Nm_factor.between(999,1001).all(),
          f"factor range={identity.observed_factor_median.min():.6f}–{identity.observed_factor_median.max():.6f}")
    raw_identity=pd.read_csv(ROOT/"zero_states/sampled_raw_power_torque_identity.csv")
    positive=raw_identity[raw_identity.SHAFT_MechPower_kW.gt(100)]
    check("V3Q08","Raw sampled power agrees numerically with torque times shaft RPM at kN-m factor",
          len(positive)>400 and positive.identity_error_kw.abs().mean()<10,
          f"n={len(positive)}; raw MAE={positive.identity_error_kw.abs().mean():.3f} kW")
    shifts=pd.read_csv(ROOT/"cross_period/fold_matched_shift_decomposition.csv")
    check("V3Q09","Matched decomposition is arithmetically consistent and uses four development folds",
          len(shifts)==16 and set(shifts.fold)=={"apr","may","jun","aug"}
          and np.allclose(shifts.composition_component_kw+shifts.conditional_component_kw,
                          shifts.matched_total_shift_kw,atol=1e-8)
          and shifts.matched_n.le(shifts.validation_headline_complete_n).all(),
          f"rows={len(shifts)}")
    manifest=json.loads((ROOT/"models/v3_label_free_manifest.json").read_text())
    folds=manifest["folds"]
    months={m for _,training,val in folds for m in training+[val]}
    check("V3Q10","Model training and validation months are chronological and exclude July, November, December",
          len(folds)==4 and months=={1,2,3,4,5,6,8}
          and all(max(training)<val for _,training,val in folds)
          and manifest["no_label_calibration"] and manifest["no_torquemeter_predictors"],folds)
    paths=sorted((ROOT/"model_features").glob("dynamic_2024_*.csv.gz"))
    check("V3Q11","Dynamic feature files exist only for declared model months",
          len(paths)==7 and {int(p.stem.split("_")[-1].split(".")[0]) for p in paths}==months,
          [p.name for p in paths])
    no_leak=True;trailing=True
    for path in paths:
        month=int(path.name.split("_")[-1].split(".")[0])
        frame=pd.read_csv(path)
        source=pd.read_csv(Path("outputs/task3/data")/f"minute_2024_{month:02d}.csv.gz",
                           usecols=["window_end_utc","ME_RPM_CAMS"])
        no_leak &= (set(frame.columns).isdisjoint({"SHAFT_MechPower_kW","target_n",
                      "SHAFT_Torque_Nm_TQ","SHAFT_RPM_TQ"})
                    and frame.window_end_utc.equals(source.window_end_utc))
        for idx in [1000,min(20000,len(frame)-1)]:
            prior=source.ME_RPM_CAMS.iloc[idx-14:idx+1].dropna()
            expected_mean=prior.mean() if len(prior)>=5 else np.nan
            actual=frame.loc[idx,"ME_RPM_CAMS__mean15"]
            trailing &= (np.isnan(expected_mean) and np.isnan(actual)) or np.isclose(
                actual,expected_mean,atol=.001,rtol=1e-5)
    check("V3Q12","Saved dynamic features are aligned and contain no target or torquemeter input",
          no_leak,"Seven month tables checked")
    check("V3Q13","Sampled 15-minute means use only current and earlier feature windows",
          trailing,"Two source-reconstructed rows per model month")
    result=pd.read_csv(ROOT/"models/v3_label_free_development.csv")
    compare=pd.read_csv(ROOT/"models/v3_development_with_v2_baselines.csv")
    expected_rows=len(folds)*len(manifest["candidates"])*2
    check("V3Q14","All declared candidates have both evaluation scopes on all folds",
          len(result)==expected_rows and len(compare)==expected_rows+16
          and result.groupby(["fold","candidate"]).scope.nunique().eq(2).all(),
          f"new rows={len(result)}; comparison rows={len(compare)}")
    coverage=pd.read_csv(ROOT/"cross_period/fold_scope_coverage.csv").set_index("fold")
    counts_ok=True;metrics_ok=True
    for row in result.itertuples():
        month=row.validation_month
        source=pd.read_csv(Path("outputs/task3/data")/f"minute_2024_{month:02d}.csv.gz",
                           usecols=["SHAFT_MechPower_kW","target_n","target_min",
                                    "target_negative_n","STW_kn"])
        broad=source.target_n.gt(0)&source.STW_kn.ge(3)&source.SHAFT_MechPower_kW.notna()
        if row.scope=="headline":
            broad &= source.SHAFT_MechPower_kW.gt(0)&source.target_min.ge(0)&source.target_negative_n.eq(0)
        y=source.loc[broad,"SHAFT_MechPower_kW"].to_numpy(dtype=np.float64)
        counts_ok &= len(y)==row.n==coverage.loc[row.fold,
            "valid_headline_n" if row.scope=="headline" else "valid_broader_n"]
        r2=1-row.rmse_kw**2/np.var(y,ddof=0)
        metrics_ok &= (abs(r2-row.r2_score)<1e-8 and abs(row.bias_kw)<=row.mae_kw+1e-7
                       and row.mae_kw<=row.rmse_kw+1e-7 and -1<=row.pearson_r<=1)
    check("V3Q15","All model-scope sample counts reconcile with untouched minute targets",
          counts_ok,"32 model-fold-scope rows")
    check("V3Q16","R2, RMSE, bias, MAE and Pearson ranges are internally consistent",
          metrics_ok,"R2 recomputed from independent label variance")
    torque=pd.read_csv(ROOT/"cross_period/fold_matched_torque_rpm_diagnostic.csv")
    reference=shifts[shifts.features.str.count(r"\+")==3].sort_values(
        ["fold","caliper_train_iqr"]).reset_index(drop=True)
    observed=torque.sort_values(["fold","caliper_train_iqr"]).reset_index(drop=True)
    check("V3Q17","Torquemeter diagnostic reuses onboard-only matches and reconciles power shifts",
          len(observed)==8 and np.array_equal(observed.matched_n,reference.matched_n)
          and np.allclose(observed.validation_minus_analog_power_kw,
                          reference.conditional_component_kw,atol=1e-8)
          and observed.loc[(observed.fold=="aug")&(observed.caliper_train_iqr==.5),
                           "validation_over_analog_torque_numeric_ratio"].between(.79,.81).all(),
          "Eight development-only matched comparisons; August torque ratio near 0.80")
    output=ROOT/"v3_qa.csv"
    pd.DataFrame(ROWS).to_csv(output,index=False)
    status=pd.DataFrame(ROWS).status.value_counts().to_dict()
    print(status)
    if status.get("FAIL",0):raise SystemExit(1)


if __name__=="__main__":main()
