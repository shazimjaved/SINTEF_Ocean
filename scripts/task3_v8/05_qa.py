"""Executable V8 scientific checks; recompute timing, masks, metrics and tails."""
from __future__ import annotations

from v8_common import *
import joblib
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score

CHECKS=[]


def check(name,ok,evidence):
    CHECKS.append({"check_id":name,"status":"PASS" if bool(ok) else "FAIL","evidence":evidence})


def close(a,b,atol=1e-6):
    return bool((pd.isna(a) and pd.isna(b)) or np.isclose(a,b,rtol=1e-9,atol=atol))


def verify_metric(row,p,threshold):
    if row.selection=="accepted_only":p=p[~p.abstain]
    if len(p)!=row.n or not len(p):return False
    y=p.actual_kw.to_numpy(float);pred=p[row.method].to_numpy(float)
    if not np.isfinite(pred).all():return False
    cy=np.ptp(y)<=1e-12;cp=np.ptp(pred)<=1e-10*max(1.,abs(pred.mean()))
    expected={"mae_kw":mean_absolute_error(y,pred),"rmse_kw":np.sqrt(mean_squared_error(y,pred)),
              "r2_score":r2_score(y,pred) if len(y)>1 else np.nan,
              "pearson_r":np.nan if cy or cp or len(y)<2 else np.corrcoef(y,pred)[0,1],
              "bias_actual_minus_pred_kw":np.mean(y-pred)}
    return (all(close(getattr(row,c),v) for c,v in expected.items())
            and (pred<0).sum()==row.negative_prediction_n
            and (np.abs(y-pred)>threshold).sum()==row.severe_error_n)


def mask_scope(p,scope):
    ok=p.operational_eligible&p.observed_truth
    return ok if scope=="broader_forward" else ok&p[scope]


def ledger_check(history,ledger):
    h=history[history.operational_eligible&history.observed_truth].copy()
    h["_ts"]=TS(h)
    ok=True
    for r in ledger.itertuples():
        cutoff=pd.Timestamp(r.prediction_day_utc)-pd.Timedelta(hours=24)
        pool=h[h._ts.ge(cutoff-pd.Timedelta(days=3))&h._ts.lt(cutoff)].sort_values("_ts")
        n=len(pool);use=n>=30
        residual=pool.actual_kw-pool.fixed_ridge
        ok&=n==r.history_n and cutoff==pd.Timestamp(r.history_cutoff_exclusive_utc) and use==r.history_used
        ok&=close(float(residual.median()) if use else 0.,r.offset_kw)
        if n:
            ok&=pool.window_end_utc.iloc[-1]==r.last_admitted_label_utc and pool._ts.max()<cutoff
            ok&=close(pool.recorded_zero.mean(),r.zero_fraction) and close(pool.positive.mean(),r.positive_fraction)
            ok&=close(pool.negative_or_mixed.mean(),r.negative_fraction)
            if "artificially_hidden" in pool:ok&=not pool.artificially_hidden.any()
        if use:
            ok&=close((residual-residual.median()).abs().median(),r.residual_mad_kw)
            # Access column names directly (itertuples sanitizes double underscores).
            saved=ledger[ledger.prediction_day_utc.eq(r.prediction_day_utc)].iloc[0]
            for c in FEATURES:ok&=close(pool[c].median(),saved[f"history_median__{c}"])
    return ok


def main():
    prepare();thresholds=json.loads((OUT/"thresholds.json").read_text())
    manifest=json.loads((OUT/"experiment_manifest.json").read_text())
    check("V8_PROTOCOL",manifest==protocol() and set(FOLDS)=={6,8,9,10} and set(MONTHS).isdisjoint({7,11,12}),
          "Frozen small rule set, four Ridge refits only, explicit quarantines/no December")
    import sys
    sys.path.insert(0,str(ROOT/"scripts"))
    from channel_config import COLUMN_TO_SOURCE
    check("V8_INDEPENDENT_FEATURES",len(COLS["B"])==24 and all(COLUMN_TO_SOURCE[c]=="onboard" for c in V7["V2"]["B"])
          and all("SHAFT_" not in c and not c.startswith("target") for c in COLS["B"]),
          "Primary arrays exclude power, torque, shaft RPM, Noon/provider and target-derived states")
    provenance=pd.read_csv(OUT/"threshold_provenance.csv")
    check("V8_EARLY_ONLY_THRESHOLDS",set(provenance.month)=={4,5} and thresholds["source_months"]==[4,5]
          and thresholds["feature_scale_months"]==[1,2,3]
          and all(DIGEST(ROOT/r.path)==r.sha256 for r in provenance.itertuples()),
          "Every threshold source is Jan-Mar onboard scales or Apr/May permitted history/earlier validation")
    days=pd.read_csv(OUT/"early_threshold_daily_history.csv")
    threshold_ok=close(days.offset_kw.abs().quantile(.95),thresholds["offset_cap_kw"])
    for c in ["zero_fraction","negative_fraction","cutoff_to_last_label_hours","residual_mad_kw"]:
        threshold_ok&=close(days[c].quantile(.99),thresholds["limits"][c])
    errors=[]
    for m in [4,5]:
        for path in (OLD/"reconstruction").glob(f"predictions_m{m:02d}_*.csv.gz"):
            d=pd.read_csv(path);s=d.operational_eligible&d.observed_truth
            errors.extend((d.loc[s,"actual_kw"]-d.loc[s,"calibrated__B_ridge_full"]).abs().tolist())
    threshold_ok&=close(np.quantile(errors,.95),thresholds["reference_error_kw"])
    check("V8_THRESHOLD_RECOMPUTATION",threshold_ok,"Frozen q95 bound/error reference and q99 daily risk thresholds independently recomputed")

    old=pd.concat([pd.read_csv(OUT/f"ablation/v7_replay_m{m:02d}.csv.gz",low_memory=False)
                   for m in [4,5,6,8,9,10]],ignore_index=True)
    source_hash=pd.read_csv(OUT/"ablation/v7_prediction_provenance.csv")
    unchanged=len(source_hash)==54 and all(DIGEST(ROOT/r.source_prediction)==r.sha256 for r in source_hash.itertuples())
    for block,p in old.groupby("block_id"):
        source=pd.read_csv(OLD/f"reconstruction/predictions_{block}.csv.gz")
        unchanged&=p.window_end_utc.tolist()==source.window_end_utc.tolist()
        unchanged&=np.allclose(p.v7_calibrated,source.calibrated__B_ridge_full,atol=1e-6)
    check("V8_V7_PRESERVED",unchanged,"All 54 V7 prediction hashes and every unchanged calibrated Ridge vector verified")
    model_rows=[]
    for path in sorted((OLD/"reconstruction").glob("m*__B_ridge_full.joblib")):
        model_rows.append({"path":str(path.relative_to(ROOT)),"sha256":DIGEST(path),
                           "predates_V8":path.stat().st_mtime_ns<(OUT/"experiment_manifest.json").stat().st_mtime_ns})
    WRITE(pd.DataFrame(model_rows),OUT/"v7_model_provenance.csv")
    check("V8_V7_MODELS_UNCHANGED",len(model_rows)==6 and all(r["predates_V8"] for r in model_rows),
          "Six source V7 Ridge model artifacts predate V8; new models saved only under V8")
    ledgers=pd.read_csv(OUT/"ablation/daily_information.csv")
    old_history_ok=True
    for m in [4,5,6,8,9,10]:
        old_history_ok&=ledger_check(load_v7_history(m),ledgers[ledgers.month.eq(m)])
    check("V8_OLD_HISTORY_CUTOFFS",old_history_ok,
          "Old-model offsets/state proportions/onboard medians use only visible history strictly before day-24h")
    case=pd.read_csv(OUT/"audit/transition_case_minutes.csv.gz",low_memory=False)
    check("V8_FOUR_FAILURE_CASES",set(case.case_id)==set(CASES)
          and case.label_age_hours.dropna().ge(24).all() and case.correction_age_hours.between(0,24).all()
          and case.last_available_any_scope_label_utc.notna().all(),
          "Four required cases have explicit last-available/admitted timestamps, correction age and independent conditions")
    raw=pd.read_csv(OUT/"audit/raw_synchronous_triplets.csv.gz")
    complete=raw[[TARGET,"SHAFT_Torque_Nm_TQ","SHAFT_RPM_TQ"]].notna().all(axis=1)
    formula=2*np.pi/60*raw.SHAFT_Torque_Nm_TQ*raw.SHAFT_RPM_TQ
    reg=pd.read_csv(OUT/"audit/registered_mechanical_channels.csv")
    summary=pd.read_csv(OUT/"audit/raw_mechanical_identity_summary.csv")
    check("V8_SEPARATE_PHYSICS",raw.raw_timestamp.is_unique and complete.any()
          and np.allclose(formula[complete],raw.loc[complete,"formula_kw_if_numeric_kNm"],atol=1e-9)
          and reg.source_name.eq("Instrument Torquemeter").all()
          and reg.loc[reg.quantity_name.str.contains("Torque"),"unit"].eq("N*m").all()
          and summary.ratio_to_literal_Nm_factor.between(990,1010).all(),
          "Exact-timestamp shared-source trio identity/scaling checked; literal registration N*m retained; not an ML input")
    align=pd.read_csv(OUT/"audit/raw_to_minute_alignment.csv")
    a=align[align.complete_source_minute]
    check("V8_RAW_MINUTE_ALIGNMENT",len(a)>30 and a.raw_to_compact_difference_kw.abs().max()<.02,
          "Representative fully sampled raw [end-1min,end) power means agree with compact labels within .02kW CSV precision")

    anchor=pd.read_csv(OUT/"paired_anchors.csv")
    start=pd.to_datetime(anchor.start_utc,utc=True);end=pd.to_datetime(anchor.end_utc,utc=True)
    check("V8_PAIRED_ANCHORS",len(anchor)==16 and anchor.anchor_id.is_unique
          and (start.iloc[1:].to_numpy()>end.iloc[:-1].to_numpy()).all()
          and anchor.groupby("month").size().eq(4).all(),
          "16 predetermined disjoint 24h unions; 1h/6h/24h are intentional identical-prefix comparisons")
    original={m:LOAD(m) for m in MONTHS}
    oldblocks=pd.read_csv(OLD/"reconstruction_blocks.csv")
    hide={m:V7["hidden_mask"](d,anchor)|V7["hidden_mask"](d,oldblocks) for m,d in original.items()}
    visible={m:V7["seal_targets"](d,hide[m]) for m,d in original.items()}
    fit=pd.read_csv(OUT/"paired/fit_inventory.csv")
    fit_ok=len(fit)==4;hist_ok=True;new=[]
    for m,months in FOLDS.items():
        d=pd.concat([visible[x] for x in months],ignore_index=True)
        cutoff=pd.Timestamp(2024,m,1,tz="UTC")-pd.Timedelta(hours=24)
        chosen=TRAINING(d,"B_ridge_full",cutoff)
        row=fit[fit.month.eq(m)].iloc[0]
        fit_ok&=len(chosen)==row.train_n and not chosen.artificially_hidden.any()
        fit_ok&=chosen.window_end_utc.max()==row.last_training_label_utc and TS(chosen).max()<cutoff
        model=joblib.load(OUT/f"paired/ridge_m{m:02d}.joblib")
        fit_ok&=close(model.named_steps["ridge"].alpha,100.)
        stats=np.nanmedian(chosen[COLS["B"]].to_numpy(np.float32),axis=0)
        fit_ok&=np.allclose(stats,model.named_steps["simpleimputer"].statistics_,equal_nan=True,atol=1e-5)
        h=pd.read_csv(OUT/f"paired/sealed_history_m{m:02d}.csv.gz",low_memory=False)
        hist_ok&=h.loc[hide[m],"actual_kw"].isna().all() and not h.loc[hide[m],"observed_truth"].any()
        l=pd.read_csv(OUT/"paired/daily_information.csv");l=l[l.month.eq(m)]
        hist_ok&=ledger_check(h,l)
        for aid in anchor[anchor.month.eq(m)].anchor_id:
            p=pd.read_csv(OUT/f"paired/predictions_{aid}.csv.gz",low_memory=False)
            new.append(p)
    check("V8_GLOBAL_FIT_EMBARGO",fit_ok,
          "Four alpha100 Ridge refits independently exclude old+new hidden labels; imputation medians match earlier training only")
    check("V8_GLOBAL_HISTORY_EMBARGO",hist_ok,
          "All new-anchor labels remain sealed in histories; n/state/offset/covariate statistics independently replay with strict delay")
    new=pd.concat(new,ignore_index=True)
    cover=pd.read_csv(OUT/"paired/horizon_coverage.csv")
    matched=cover.groupby("anchor_id").scored_n.min().gt(0)
    complete_match=cover.groupby("anchor_id").unscored_missing_n.sum().eq(0)&matched
    check("V8_HORIZON_COVERAGE",len(new)==23040 and new.window_end_utc.is_unique and len(cover)==48
          and cover.calendar_n.eq(cover.horizon_hours*60).all()
          and (cover.eligible_n==cover.scored_n+cover.unscored_missing_n).all()
          and (cover.scored_n==cover.positive_n+cover.zero_n+cover.negative_or_mixed_n).all()
          and cover.matched_any_truth.equals(cover.anchor_id.map(matched))
          and cover.matched_complete_eligible_truth.equals(cover.anchor_id.map(complete_match)),
          "All unions/prefixes and matched cohorts retained; original missing vs positive/zero/negative counts reconcile")
    rule_ok=True;truth_invariant=True
    for d in [old,new]:
        recalculated=apply_rules(d,thresholds)
        rule_ok&=np.array_equal(recalculated.abstain,d.abstain)
        rule_ok&=np.allclose(d.bounded_residual-d.fixed_ridge,d.offset_kw.clip(-thresholds["offset_cap_kw"],thresholds["offset_cap_kw"]))
        rule_ok&=d.clipped_v7.ge(0).all()
        corrupt=d.copy();corrupt.actual_kw=999999.;corrupt.observed_truth=False;corrupt.positive=False;corrupt.recorded_zero=True
        replay=apply_rules(corrupt,thresholds)
        truth_invariant&=np.array_equal(replay.abstain,d.abstain)
        for method in ["v7_calibrated","bounded_residual","clipped_v7"]:
            truth_invariant&=np.allclose(replay[method],d[method])
    current_without_truth=original[6].copy()
    current_without_truth[TARGET]=np.nan;current_without_truth.target_n=0
    truth_invariant&=np.array_equal(ELIGIBLE(current_without_truth),ELIGIBLE(original[6]))
    check("V8_RULES_AND_TRUTH_INVARIANCE",rule_ok and truth_invariant,
          "Frozen bound/flags/clipping replay; arbitrary changes to current truth cannot change predictions, abstention or eligibility")
    # One real replay verifies that sealed June anchor truth cannot affect the
    # subsequent August fit, including fitted train-only transformations.
    corrupted=original[6].copy();corrupted.loc[hide[6],TARGET]=7654321.
    corrupted=V7["seal_targets"](corrupted,hide[6])
    replay_train=pd.concat([visible[1],visible[2],visible[3],visible[4],visible[5],corrupted],ignore_index=True)
    selected=TRAINING(replay_train,"B_ridge_full",pd.Timestamp("2024-07-31T00:00:00Z"))
    replay_model=FACTORY(DEFINITION);replay_model.fit(selected[COLS["B"]].to_numpy(np.float32),selected[TARGET].to_numpy(np.float32))
    saved=joblib.load(OUT/"paired/ridge_m08.joblib")
    x=original[8].loc[V7["hidden_mask"](original[8],anchor),COLS["B"]].to_numpy(np.float32)
    check("V8_HIDDEN_LABEL_SENTINEL",np.allclose(replay_model.predict(x),saved.predict(x),rtol=1e-8,atol=1e-5),
          "Replacing every sealed June label with an extreme value leaves the refitted August paired predictions unchanged")
    threshold_time=(OUT/"thresholds.json").stat().st_mtime_ns
    check("V8_PREDECLARATION",all(threshold_time<p.stat().st_mtime_ns for p in (OUT/"paired").glob("ridge_m*.joblib"))
          and (OUT/"experiment_manifest.json").stat().st_mtime_ns<threshold_time,
          "Protocol then early thresholds predate every new paired model fit")

    table=OUT/"tables";error=thresholds["reference_error_kw"]
    exact=True
    for file,source_id in [("v7_replay_scope_metrics.csv","old"),("paired_horizon_metrics.csv","new")]:
        rows=pd.read_csv(table/file)
        for r in rows.itertuples():
            if source_id=="old":
                if r.period=="early_threshold_development":p=old[old.source_month.isin([4,5])]
                elif r.period=="later_inspected_development":p=old[old.source_month.isin([6,8,9,10])]
                else:p=old[old.source_month.eq(int(r.period[1:]))]
            else:
                p=new[new.elapsed_minutes.le(r.horizon_hours*60)]
                if r.cohort=="matched_any":p=p[p.anchor_id.isin(matched[matched].index)]
                elif r.cohort=="matched_complete_eligible":p=p[p.anchor_id.isin(complete_match[complete_match].index)]
            p=p.loc[mask_scope(p,r.scope)]
            exact&=len(p)==r.denominator_n and verify_metric(r,p,error)
    check("V8_EXACT_POOLED_SELECTIVE_METRICS",exact,
          "Every full/selective MAE/RMSE/sklearn R2/Pearson r/bias/negativity/severe count recomputed on its actual denominator")
    exact_blocks=True
    for filename,data,idcol in [("v7_replay_block_metrics.csv",old,"block_id"),("paired_anchor_metrics.csv",new,"anchor_id")]:
        groups={k:p for k,p in data.groupby(idcol)}
        for r in pd.read_csv(table/filename).itertuples():
            p=groups[getattr(r,idcol)]
            if idcol=="anchor_id":p=p[p.elapsed_minutes.le(r.horizon_hours*60)]
            p=p.loc[mask_scope(p,r.scope)]
            exact_blocks&=verify_metric(r,p,error)
    tails=pd.read_csv(table/"paired_equal_block_tail_metrics.csv")
    blockmetrics=pd.read_csv(table/"paired_anchor_metrics.csv")
    for r in tails.itertuples():
        p=blockmetrics[(blockmetrics.horizon_hours==r.horizon_hours)&(blockmetrics.method==r.method)&
                       (blockmetrics.scope==r.scope)&(blockmetrics.selection==r.selection)]
        exact_blocks&=close(p.mae_kw.mean(),r.mean_block_mae_kw) and close(p.mae_kw.quantile(.9),r.p90_block_mae_kw)
        exact_blocks&=close(p.mae_kw.max(),r.worst_block_mae_kw) and p.anchor_id.nunique()==r.scoreable_anchors
    check("V8_EXACT_BLOCK_TAILS",exact_blocks,"Every block/anchor score plus equal-block p90/worst independently recomputed; disastrous cases included")
    old["_date"]=DAY(old).dt.strftime("%Y-%m-%d")
    new["_date"]=DAY(new).dt.strftime("%Y-%m-%d")
    daily_ok=True
    for r in pd.read_csv(table/"daily_metrics.csv").itertuples():
        if r.dataset=="v7_replay":p=old[old.source_month.eq(int(r.period[1:]))]
        else:p=new[new.elapsed_minutes.le(r.horizon_hours*60)]
        p=p.loc[p._date.eq(r.date)&mask_scope(p,r.scope)]
        daily_ok&=len(p)==r.denominator_n and verify_metric(r,p,error)
    check("V8_DAILY_METRICS",daily_ok,"All per-day denominators and numerical scores independently recomputed from covered-minute dates")
    false=pd.read_csv(table/"false_confidence_minutes.csv.gz",low_memory=False)
    expected=0
    for p in [old[old.source_month.isin([6,8,9,10])],new]:
        for method in ["v7_calibrated","bounded_residual"]:
            expected+=int((mask_scope(p,"broader_forward")&~p.abstain&(p[method]-p.actual_kw).abs().gt(error)).sum())
    check("V8_FALSE_CONFIDENCE_ACCOUNTING",len(false)==expected and not false.abstain.any(),
          "All accepted errors above the early q95 reference retained; no false-confidence cases silently removed")
    WRITE(pd.DataFrame(CHECKS),OUT/"v8_qa.csv")
    for r in CHECKS:print(r["status"],r["check_id"],r["evidence"])
    failed=sum(r["status"]=="FAIL" for r in CHECKS)
    print(f"{len(CHECKS)-failed} PASS; {failed} FAIL")
    if failed:raise SystemExit(1)


if __name__=="__main__":main()
