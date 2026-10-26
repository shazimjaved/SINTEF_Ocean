"""Check target derivation and the apparent torque-unit scale using raw data.

Torquemeter channels are used only for target diagnostics, never prediction.
The registered PDF says torque N*m; the factor expected for N*m is compared
with the observed numeric factor without changing the source dictionary.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path("outputs/task3_v3/zero_states")
FACTOR_NM=2*np.pi/60000
FACTOR_KNM=2*np.pi/60


def main():
    minute=pd.read_csv(ROOT/"torquemeter_minute_audit_2024.csv.gz")
    p=minute.SHAFT_MechPower_kW.to_numpy(dtype=np.float64)
    t=minute.SHAFT_Torque_Nm_TQ.to_numpy(dtype=np.float64)
    r=minute.SHAFT_RPM_TQ.to_numpy(dtype=np.float64)
    cams=minute.ME_RPM_CAMS.to_numpy(dtype=np.float64)
    keep=(p>100)&(t>1)&(r>10)&np.isfinite(cams)&(cams>10)
    identity=minute.loc[keep,["source_month","window_end_utc"]].copy()
    identity["observed_kw"]=p[keep]
    identity["formula_kw_if_numeric_torque_is_kNm"]=FACTOR_KNM*t[keep]*r[keep]
    identity["formula_kw_if_PDF_Nm_is_literal"]=FACTOR_NM*t[keep]*r[keep]
    identity["observed_factor"]=p[keep]/(t[keep]*r[keep])
    identity["shaft_to_cams_rpm_ratio"]=r[keep]/cams[keep]
    identity["torque_numeric"]=t[keep]
    identity["fuel_load_pct"]=minute.loc[keep,"ME_FuelLoad_pct"].to_numpy()
    identity.to_csv(ROOT/"minute_positive_power_identity.csv.gz",index=False,compression="gzip")
    rows=[]
    for month,d in identity.groupby("source_month"):
        error=d.observed_kw-d.formula_kw_if_numeric_torque_is_kNm
        rows.append({"month":month,"n":len(d),
                     "observed_factor_median":float(d.observed_factor.median()),
                     "observed_factor_p01":float(d.observed_factor.quantile(.01)),
                     "observed_factor_p99":float(d.observed_factor.quantile(.99)),
                     "ratio_to_literal_Nm_factor":float(d.observed_factor.median()/FACTOR_NM),
                     "formula_mean_abs_error_kw":float(error.abs().mean()),
                     "formula_median_abs_error_kw":float(error.abs().median()),
                     "shaft_to_cams_ratio_median":float(d.shaft_to_cams_rpm_ratio.median()),
                     "torque_numeric_median":float(d.torque_numeric.median())})
    summary=pd.DataFrame(rows)
    summary.to_csv(ROOT/"monthly_power_torque_identity.csv",index=False)
    raw=pd.read_csv(ROOT/"selected_raw_readings.csv.gz")
    trio=raw[raw.channel.isin(["SHAFT_MechPower_kW","SHAFT_Torque_Nm_TQ","SHAFT_RPM_TQ"])]
    wide=trio.pivot_table(index=["episode","boundary","offset_min","raw_timestamp"],
                          columns="channel",values="value",aggfunc="first").dropna().reset_index()
    wide["formula_kw_if_numeric_torque_is_kNm"]=(FACTOR_KNM*wide.SHAFT_Torque_Nm_TQ*wide.SHAFT_RPM_TQ)
    wide["identity_error_kw"]=(wide.SHAFT_MechPower_kW-
                                wide.formula_kw_if_numeric_torque_is_kNm)
    wide["power_zero"]=wide.SHAFT_MechPower_kW.eq(0)
    wide["torque_zero"]=wide.SHAFT_Torque_Nm_TQ.eq(0)
    wide["rpm_zero"]=wide.SHAFT_RPM_TQ.eq(0)
    wide.to_csv(ROOT/"sampled_raw_power_torque_identity.csv",index=False)
    positive=wide[wide.SHAFT_MechPower_kW.gt(100)&wide.SHAFT_Torque_Nm_TQ.gt(1)
                  &wide.SHAFT_RPM_TQ.gt(10)]
    assert len(positive)>100
    assert (wide.power_zero==wide.torque_zero).mean()>.99
    assert (wide.power_zero==wide.rpm_zero).mean()>.99
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    axes[0].plot(summary.month,summary.observed_factor_median,marker="o",label="Observed")
    axes[0].axhline(FACTOR_KNM,color="darkgreen",linestyle="--",label="If numeric torque is kN·m")
    axes[0].axhline(FACTOR_NM,color="darkred",linestyle=":",label="Literal PDF N·m")
    axes[0].set(ylabel="P/(torque × shaft RPM)",xlabel="2024 month",
                title="Power conversion factor is stable")
    axes[0].legend(fontsize=7)
    axes[1].plot(summary.month,summary.shaft_to_cams_ratio_median,marker="o")
    axes[1].axhline(1,color="0.4",linestyle="--")
    axes[1].set(ylabel="Median shaft RPM / CAMS RPM",xlabel="2024 month",
                title="Positive-power RPM relation")
    fig.tight_layout();fig.savefig(ROOT/"power_torque_identity_monthly.png",dpi=170)
    plt.close(fig)
    print(summary[["month","n","observed_factor_median","ratio_to_literal_Nm_factor",
                   "formula_mean_abs_error_kw","shaft_to_cams_ratio_median"]].to_string(index=False))
    print({"sampled_raw_triplets":len(wide),"positive_triplets":len(positive),
           "positive_raw_formula_mae_kw":float(positive.identity_error_kw.abs().mean()),
           "zero_trio_agreement_pct":100*float((wide.power_zero&wide.torque_zero&wide.rpm_zero).sum()/wide.power_zero.sum())})


if __name__=="__main__":main()
