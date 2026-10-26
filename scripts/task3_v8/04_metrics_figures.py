"""All-observation, selective, transition and matched-anchor V8 evaluation."""
from __future__ import annotations

from v8_common import *
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def stats(part,method,common,selection="all_predictions"):
    accepted=part.loc[~part.abstain] if selection=="accepted_only" else part
    if not len(accepted):return None
    p=accepted[method].to_numpy(float);y=accepted.actual_kw.to_numpy(float)
    assert np.isfinite(p).all()
    threshold=json.loads((OUT/"thresholds.json").read_text())["reference_error_kw"]
    return {**common,"method":method,"selection":selection,
            **METRIC(y,p),"denominator_n":len(part),"observed_acceptance_fraction":len(accepted)/len(part),
            "negative_prediction_n":int((p<0).sum()),"negative_prediction_fraction":float((p<0).mean()),
            "severe_error_n":int((np.abs(y-p)>threshold).sum()),
            "severe_error_fraction":float((np.abs(y-p)>threshold).mean())}


def evaluate(frame,common):
    out=[]
    for scope,mask in scopes(frame).items():
        p=frame.loc[mask]
        if not len(p):continue
        for method in METHODS:
            r=stats(p,method,{**common,"scope":scope})
            out.append(r)
            if method in ["v7_calibrated","bounded_residual"]:
                r=stats(p,method,{**common,"scope":scope},"accepted_only")
                if r:out.append(r)
    return out


def coverage(frame,common):
    e=frame.operational_eligible;s=e&frame.observed_truth;a=~frame.abstain
    return {**common,"calendar_n":len(frame),"eligible_n":int(e.sum()),"scored_n":int(s.sum()),
            "unscored_missing_n":int((e&~frame.observed_truth).sum()),
            "positive_n":int((s&frame.positive).sum()),"zero_n":int((s&frame.recorded_zero).sum()),
            "negative_or_mixed_n":int((s&frame.negative_or_mixed).sum()),
            "accepted_eligible_n":int((e&a).sum()),"accepted_observed_n":int((s&a).sum()),
            "accepted_positive_n":int((s&a&frame.positive).sum()),"accepted_zero_n":int((s&a&frame.recorded_zero).sum()),
            "target_independent_acceptance_fraction":float((e&a).sum()/e.sum()) if e.any() else np.nan,
            "interval_reference_coverage":float((frame.loc[s,"actual_kw"].ge(frame.loc[s,"reference_interval_low_kw"]) &
                 frame.loc[s,"actual_kw"].le(frame.loc[s,"reference_interval_high_kw"])).mean()) if s.any() else np.nan}


def main():
    prepare();dest=OUT/"tables";dest.mkdir(exist_ok=True)
    figdir=OUT/"figures";figdir.mkdir(exist_ok=True)
    old=pd.concat([pd.read_csv(OUT/f"ablation/v7_replay_m{m:02d}.csv.gz",low_memory=False)
                   for m in [4,5,6,8,9,10]],ignore_index=True)
    old["date"]=DAY(old).dt.strftime("%Y-%m-%d")
    records=[];covered=[];daily=[];perblock=[];false=[]
    for period,p in [("early_threshold_development",old[old.source_month.isin([4,5])]),
                     ("later_inspected_development",old[old.source_month.isin([6,8,9,10])])]:
        records.extend(evaluate(p,{"dataset":"v7_replay","period":period}))
        covered.append(coverage(p,{"dataset":"v7_replay","period":period}))
    for month,p in old.groupby("source_month"):
        records.extend(evaluate(p,{"dataset":"v7_replay","period":f"m{month:02d}"}))
        covered.append(coverage(p,{"dataset":"v7_replay","period":f"m{month:02d}"}))
        for day,q in p.groupby("date"):
            daily.extend(evaluate(q,{"dataset":"v7_replay","period":f"m{month:02d}","date":day}))
    for block,p in old.groupby("block_id"):
        perblock.extend(evaluate(p,{"dataset":"v7_replay","block_id":block,
                                   "period":f"m{int(p.source_month.iloc[0]):02d}"}))
        if block in CASES:
            covered.append(coverage(p,{"dataset":"transition_case","period":block}))
    WRITE(pd.DataFrame(records),dest/"v7_replay_scope_metrics.csv")
    WRITE(pd.DataFrame(perblock),dest/"v7_replay_block_metrics.csv")
    case_rows=[r for r in perblock if r["block_id"] in CASES]
    WRITE(pd.DataFrame(case_rows),dest/"transition_ablation_metrics.csv")

    frames=[]
    for path in sorted((OUT/"paired").glob("predictions_m*.csv.gz")):
        p=pd.read_csv(path,low_memory=False);p["date"]=DAY(p).dt.strftime("%Y-%m-%d");frames.append(p)
    full=pd.concat(frames,ignore_index=True)
    assert full.window_end_utc.is_unique
    ccover=pd.read_csv(OUT/"paired/horizon_coverage.csv")
    matched_any=set(ccover[ccover.matched_any_truth].anchor_id)
    matched_complete=set(ccover[ccover.matched_complete_eligible_truth].anchor_id)
    paired_rows=[];anchor_rows=[]
    for horizon in [1,6,24]:
        prefix=full[full.elapsed_minutes.le(horizon*60)]
        for cohort,ids in [("all_available",set(full.anchor_id)),("matched_any",matched_any),
                           ("matched_complete_eligible",matched_complete)]:
            p=prefix[prefix.anchor_id.isin(ids)]
            if not len(p):continue
            common={"dataset":"paired","cohort":cohort,"horizon_hours":horizon}
            paired_rows.extend(evaluate(p,common));covered.append(coverage(p,{**common,"period":"all"}))
        for anchor,p in prefix.groupby("anchor_id"):
            common={"dataset":"paired","anchor_id":anchor,"horizon_hours":horizon,
                    "period":f"m{int(p.source_month.iloc[0]):02d}"}
            anchor_rows.extend(evaluate(p,common))
        # Per-day stability is evaluated once per horizon; these nested prefix
        # cases must never be pooled as independent repeated observations.
        for day,p in prefix.groupby("date"):
            daily.extend(evaluate(p,{"dataset":"paired","period":"all","horizon_hours":horizon,"date":day}))
    WRITE(pd.DataFrame(paired_rows),dest/"paired_horizon_metrics.csv")
    anchor_metrics=pd.DataFrame(anchor_rows)
    WRITE(anchor_metrics,dest/"paired_anchor_metrics.csv")
    tails=anchor_metrics.groupby(["horizon_hours","method","scope","selection"]).agg(
        scoreable_anchors=("anchor_id","nunique"),mean_block_mae_kw=("mae_kw","mean"),
        median_block_mae_kw=("mae_kw","median"),p90_block_mae_kw=("mae_kw",lambda x:x.quantile(.9)),
        worst_block_mae_kw=("mae_kw","max"),minute_weighted_denominator=("n","sum")).reset_index()
    WRITE(tails,dest/"paired_equal_block_tail_metrics.csv")
    oldtails=pd.DataFrame(perblock)
    oldtails=oldtails[oldtails.period.isin(["m06","m08","m09","m10"])]
    oldtails=oldtails.groupby(["method","scope","selection"]).agg(scoreable_blocks=("block_id","nunique"),
        mean_block_mae_kw=("mae_kw","mean"),p90_block_mae_kw=("mae_kw",lambda x:x.quantile(.9)),
        worst_block_mae_kw=("mae_kw","max")).reset_index()
    WRITE(oldtails,dest/"v7_later_block_tail_metrics.csv")
    WRITE(pd.DataFrame(covered),dest/"eligibility_abstention_coverage.csv")
    WRITE(pd.DataFrame(daily),dest/"daily_metrics.csv")
    reference=json.loads((OUT/"thresholds.json").read_text())["reference_error_kw"]
    for dataset,p in [("v7_later",old[old.source_month.isin([6,8,9,10])]),("paired_24h_unions",full)]:
        for method in ["v7_calibrated","bounded_residual"]:
            mask=p.operational_eligible&p.observed_truth&~p.abstain&(p[method]-p.actual_kw).abs().gt(reference)
            q=p.loc[mask].copy();q["dataset"]=dataset;q["method"]=method
            q["absolute_error_kw"]=(q[method]-q.actual_kw).abs();false.append(q)
    WRITE(pd.concat(false,ignore_index=True),dest/"false_confidence_minutes.csv.gz")
    # Within-anchor comparisons always use exactly the same rows and scope.
    primary=anchor_metrics[anchor_metrics.selection.eq("all_predictions")]
    ref=primary[primary.method.eq("v7_calibrated")][["anchor_id","horizon_hours","scope","mae_kw","rmse_kw"]].rename(
        columns={"mae_kw":"reference_v7_mae_kw","rmse_kw":"reference_v7_rmse_kw"})
    paired_delta=primary.merge(ref,on=["anchor_id","horizon_hours","scope"],validate="many_to_one")
    paired_delta["delta_mae_vs_v7_kw"]=paired_delta.mae_kw-paired_delta.reference_v7_mae_kw
    WRITE(paired_delta,dest/"paired_same_anchor_comparisons.csv")

    fig,axs=plt.subplots(2,2,figsize=(11,7))
    show=["v7_calibrated","bounded_residual","clipped_v7","delayed_persistence"]
    for ax,case in zip(axs.ravel(),CASES):
        p=pd.DataFrame(case_rows)
        p=p[(p.block_id==case)&(p.scope=="broader_forward")&(p.selection=="all_predictions")].set_index("method")
        ax.bar(np.arange(4),p.loc[show,"mae_kw"],color=["#1f77b4","#d62728","#9467bd","#2ca02c"])
        cv=next(r for r in covered if r.get("dataset")=="transition_case" and r["period"]==case)
        ax.set_title(f"{case}: n={int(p.n.iloc[0])}, accepted={cv['accepted_observed_n']}, zeros={cv['zero_n']}",fontsize=9)
        ax.set_xticks(np.arange(4),["V7","Bounded","Clipped V7","Persistence"],rotation=15)
        ax.set_ylabel("MAE (kW)");ax.grid(axis="y",alpha=.2)
    fig.suptitle("Four inspected V7 transition failures; thresholds developed in April/May")
    fig.tight_layout();fig.savefig(figdir/"transition_failure_ablation.png",dpi=170);plt.close(fig)

    metrics=pd.DataFrame(paired_rows)
    fig,axs=plt.subplots(1,2,figsize=(11.5,4.7))
    for ax,cohort in zip(axs,["all_available","matched_any"]):
        for method in ["v7_calibrated","bounded_residual","delayed_persistence","delayed_history_mean"]:
            p=metrics[(metrics.cohort==cohort)&(metrics.method==method)&metrics.scope.eq("broader_forward")&metrics.selection.eq("all_predictions")].sort_values("horizon_hours")
            ax.plot(p.horizon_hours,p.mae_kw,marker="o",label=method.replace("_"," "))
        ns=metrics[(metrics.cohort==cohort)&metrics.method.eq("v7_calibrated")&metrics.scope.eq("broader_forward")&metrics.selection.eq("all_predictions")].sort_values("horizon_hours")
        ax.set_xticks([1,6,24],[f"{int(h)}h\nn={int(n):,}" for h,n in zip(ns.horizon_hours,ns.n)])
        ax.set(title=cohort.replace("_"," "),ylabel="MAE (kW)",xlabel="Paired prefix horizon")
        ax.grid(alpha=.2)
    axs[0].legend(fontsize=8)
    fig.suptitle("Same anchors and common 24h embargo; horizons include different future operating minutes")
    fig.tight_layout();fig.savefig(figdir/"paired_prefix_comparison.png",dpi=170);plt.close(fig)

    r=pd.DataFrame(records)
    selective=r[r.period.isin(["m06","m08","m09","m10"])&r.scope.eq("broader_forward")&r.selection.eq("accepted_only")&r.method.eq("v7_calibrated")]
    fig,ax=plt.subplots(figsize=(6.8,4.5))
    for row in selective.itertuples():
        ax.scatter(100*row.observed_acceptance_fraction,100*row.severe_error_fraction,s=60)
        ax.annotate(row.period,(100*row.observed_acceptance_fraction,100*row.severe_error_fraction),xytext=(4,4),textcoords="offset points")
    zero_old=r[(r.period=="later_inspected_development")&r.scope.eq("recorded_zero")&
               r.selection.eq("accepted_only")&r.method.eq("v7_calibrated")]
    zero_new=metrics[(metrics.cohort=="all_available")&metrics.horizon_hours.eq(24)&metrics.scope.eq("recorded_zero")&
                     metrics.selection.eq("accepted_only")&metrics.method.eq("v7_calibrated")]
    for label,source in [("V7 later zeros",zero_old),("Paired 24h zeros",zero_new)]:
        if len(source):
            row=source.iloc[0]
            ax.scatter(100*row.observed_acceptance_fraction,100*row.severe_error_fraction,marker="^",s=80,c="black")
            ax.annotate(f"{label} (n={int(row.n)})",(100*row.observed_acceptance_fraction,100*row.severe_error_fraction),
                        xytext=(4,-13),textcoords="offset points",fontsize=7)
    ax.axhline(5,ls="--",c=".4",label="Early q95 error reference (not a guarantee)")
    ax.set(xlabel="Observed forward truths accepted (%)",ylabel="Accepted errors above early reference (%)",
           title="Historical-risk flag: false confidence remains measurable",xlim=(0,105),ylim=(0,105))
    ax.legend(fontsize=7);ax.grid(alpha=.2);fig.tight_layout()
    fig.savefig(figdir/"abstention_false_confidence.png",dpi=170);plt.close(fig)
    print("PASS: all-row and selective metrics, matched-anchor coverage, tails, negativity and false-confidence evidence saved")


if __name__=="__main__":main()
