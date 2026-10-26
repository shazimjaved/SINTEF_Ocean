"""Bounded internal source/transition audit. No fitting, target changes or reports.

Run from the project root with python -X utf8 -B .../01_audit.py STAGE.
Stages: prepare, events, windows, analyse, finish. Existing stage outputs are
immutable; inspect failures rather than overwriting a completed experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
assert Path.cwd().resolve() == ROOT
sys.path.insert(0, str(ROOT / "scripts"))
from channel_config import ANGLE_COLUMNS, COLUMN_TO_QID, TARGET

OUT = ROOT / "outputs/task3_source_audit"
MINUTE = pd.Timedelta(minutes=1)
HALF = pd.Timedelta(minutes=10)
MATCH = ["STW_kn", "SOG_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct",
         "ME_ScavAirPressure_bar", "ME_TC_RPM_Transducer"]
INDEPENDENT = MATCH + ["WIND_RelSpeed_kn", "WIND_RelAngle_deg",
                       "HULL_HeadingTrue_deg", "HULL_TurnRate_degmin"]
STATISTICS = ["level_delta", "edge_delta", "sd_delta", "within_minute_sd_delta",
              "cadence_delta_s", "max_gap_delta_s", "phase_delta_s", "count_delta"]
EVENT_FILE = ROOT / "outputs/task3_v3/zero_states/raw_mechanical_switch_events.csv"
RUN_FILE = ROOT / "outputs/task3_v2/phase1/zero_power_runs_yearwide.csv"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write(frame, name):
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    frame.to_csv(path, index=False)


def write_json(value, name):
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def originals():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", "outputs/task3_source_audit/", "scripts/task3_source_audit/")):
            continue
        yield p


def source_inventory():
    import fitz
    evidence = []
    deck = ROOT / "docs/challenge/Big Data from ships Challenge V1.pptx"
    with ZipFile(deck) as z:
        slide = " ".join(ET.fromstring(z.read("ppt/slides/slide6.xml")).itertext())
    assert "4/5" in slide and "extra challenges" in slide
    evidence.append({"source": deck.relative_to(ROOT).as_posix(), "location": "slide 6",
                     "evidence": slide[:400], "classification": "announced design; not release verification"})
    for filename, terms in [
        ("docs/SINTEF_Ocean_v2.pdf", ["mis calibrated", "Cleaning events"]),
        ("docs/challenge/HullPIC25 Announcement.pdf", ["Cleaning events", "event labels"]),
    ]:
        with fitz.open(ROOT / filename) as doc:
            for page_number, page in enumerate(doc, 1):
                txt = " ".join(page.get_text().split())
                for term in terms:
                    at = txt.lower().find(term.lower())
                    if at >= 0:
                        evidence.append({"source": filename, "location": f"PDF page {page_number}",
                                         "evidence": txt[max(0, at - 100):at + 230],
                                         "classification": "general concern or announced event data; no interval/QID attribution"})
    write(pd.DataFrame(evidence), "source_evidence.csv")
    inventory = []
    for folder in ["docs", "data/Noon Reports"]:
        for p in sorted((ROOT / folder).rglob("*")):
            if p.is_file():
                inventory.append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size})
    write(pd.DataFrame(inventory), "source_inventory.csv")
    hits = []
    terms = ["extra challenges", "release note", "release manifest", "cleaning event",
             "miscalibrat", "mis calibrated", "injected", "altered dataset"]
    for p in originals():
        if p.suffix.lower() not in {".md", ".json", ".txt", ".yaml", ".yml"}:
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for term in terms:
            at = txt.lower().find(term)
            if at >= 0:
                hits.append({"path": p.relative_to(ROOT).as_posix(), "term": term,
                             "excerpt": " ".join(txt[max(0, at - 100):at + 220].split())})
    write(pd.DataFrame(hits, columns=["path", "term", "excerpt"]), "metadata_search_hits.csv")
    missing = [
        ("Exact release alteration/quality manifest", "Affected QIDs, UTC intervals, transformation semantics, release identifier and original truth if available"),
        ("Torquemeter status/export specification", "Meaning of zero, validity flags, clocks/filter delays, scaling and calibration"),
        ("Noon dictionary and timing", "Propulsion-consumption units, interval represented, acquisition/issuance and upstream independence"),
        ("Actual propulsion configuration", "Engine/shaft coupling and authoritative reconciliation of reference engine discrepancy"),
        ("Cleaning/event log", "Actual UTC event intervals and provenance")]
    write(pd.DataFrame(missing, columns=["missing_item", "minimum_required_content"]), "missing_metadata.csv")
    noon = pd.read_csv(ROOT / "data/Noon Reports/N08_August_Data_with_Propulsion_and_Fuel.csv")
    noon["date_parsed"] = pd.to_datetime(noon.Date, dayfirst=True)
    d = noon[noon.date_parsed.between("2024-08-27", "2024-08-31")].copy()
    d["interpretation"] = "reported context only; unit, reporting interval and independence not verified"
    write(d, "noon_context.csv")


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "audit_manifest.json").exists():
        raise FileExistsError("Prepared audit exists; do not refreeze protocol")
    protocol = {
        "scope": "bounded internal diagnostic audit; no training, relabelling or correction",
        "raw_months": [6, 8, 9], "forbidden_raw_evaluation_months": [7, 11, 12],
        "event_sources": [str(EVENT_FILE.relative_to(ROOT)), str(RUN_FILE.relative_to(ROOT))],
        "event_resolution": "verify listed June/Aug onset pairs directly in source; resolve September manifest recovery candidate in raw power before choosing independent windows",
        "events_are": "recorded-channel switches, not confirmed physical state changes",
        "window": "[verified exact switch -10min, switch +10min); diagnostics use both sides",
        "independent_channels": INDEPENDENT, "matching_channels": MATCH,
        "matching_scale": "IQR of complete independent STW>=3 Jan-Mar rows; no target filter",
        "control_schedule": "hourly same-month anchors at same minute/second offset as event; at least 24h away",
        "control_matching": "pre-anchor ten full completed-minute medians only; RMS normalized distance <=0.5 and maximum individual distance <=1; nearest 24 per state",
        "control_scopes": ["stable recorded-positive, raw minimum >0", "stable recorded-zero"],
        "control_state_selection": "retrospective diagnostic control definition only; never a deployable eligibility rule",
        "control_requirements": "full 21 enclosing minutes observed and STW>=3; 10 pre-anchor complete feature minutes; no replacement when support inadequate",
        "signature_statistics": STATISTICS,
        "signature_gate": "same channel/statistic outside full matched positive-control range with same nonzero signed change in both onsets and opposite signed change at recovery; >=12 controls each; >=30 raw samples on each event side",
        "signature_gate_interpretation": "descriptive repeatability screen only; not a significance test or validated detector; no tuning after results",
        "source_issue_gate": "new directly demonstrated processing inconsistency or authoritative release-specific issue; previously known ambiguities do not establish a new mechanism",
        "decision_priority": "A confirmed issue, else B repeatable independent signal, else C no decisive new evidence; manual review must confirm source evidence",
        "limits": "three selected events; matched controls not population false-positive estimates; no full-year integrity or impossibility claim",
        "outputs": "audit script, manifest, diagnostic CSVs, compact raw-window extracts, concise internal markdown; no report formats",
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
        "script_sha256": digest(Path(__file__)),
    }
    write_json(protocol, "audit_manifest.json")
    rows = [{"path": str(p.relative_to(ROOT).as_posix()), "bytes": p.stat().st_size,
             "sha256_before": digest(p)} for p in originals()]
    write(pd.DataFrame(rows), "original_artifact_hashes.csv")
    source_inventory()
    print(f"Prepared frozen audit; hashed {len(rows)} original artifacts", flush=True)


def stream_selected(month, prefixes, names):
    qmap = {COLUMN_TO_QID[c]: c for c in names}
    pieces = []
    for chunk in pd.read_csv(ROOT / f"data/raw/{month}.csv", header=None,
                             names=["raw_timestamp", "qid", "value"],
                             dtype={"raw_timestamp": "str", "qid": "str", "value": "float64"},
                             chunksize=100000):
        selected = chunk[chunk.qid.isin(qmap)]
        selected = selected[selected.raw_timestamp.str.slice(0, 16).isin(prefixes)]
        if len(selected):
            pieces.append(selected)
    result = pd.concat(pieces, ignore_index=True)
    result["channel"] = result.qid.map(qmap)
    result["ts"] = pd.to_datetime(result.raw_timestamp, utc=True)
    return result.sort_values(["channel", "ts"]).reset_index(drop=True)


def prefixes_between(start, stop):
    return set(pd.date_range(start.floor("min"), stop.ceil("min"), freq="min").strftime("%Y-%m-%dT%H:%M"))


def events():
    manifest = pd.read_csv(EVENT_FILE)
    pairs = manifest[(manifest.channel == TARGET) &
                     manifest.episode.isin(["run_1_20240610", "run_2_20240827"])].copy()
    assert len(pairs) == 2
    candidates = []
    for r in pairs.itertuples():
        anchor = pd.Timestamp(r.first_after_ts)
        candidates.append({"event_id": f"m{anchor.month:02d}_onset", "kind": "onset",
                           "month": anchor.month, "candidate": anchor,
                           "expected_before": r.last_before_ts, "expected_after": r.first_after_ts,
                           "source": str(EVENT_FILE.relative_to(ROOT)), "source_episode": r.episode})
    runs = pd.read_csv(RUN_FILE)
    recovery = runs[runs.start_utc.str.startswith("2024-09-10") & runs.target_after_kw.gt(100)]
    assert len(recovery) == 1, "Recovery candidate must be unique in existing manifest"
    r = recovery.iloc[0]
    candidates.append({"event_id": "m09_recovery", "kind": "recovery", "month": 9,
                       "candidate": pd.Timestamp(r.end_utc), "expected_before": "", "expected_after": "",
                       "source": str(RUN_FILE.relative_to(ROOT)), "source_episode": r.start_utc})
    write(pd.DataFrame(candidates), "event_candidates.csv")
    rows = []
    for c in candidates:
        raw = stream_selected(c["month"], prefixes_between(c["candidate"] - 2 * MINUTE,
                              c["candidate"] + 2 * MINUTE), [TARGET])
        assert not raw.duplicated(["ts", "qid"]).any()
        value = raw.value.to_numpy()
        switches = np.flatnonzero(((value[:-1] > 100) & (value[1:] == 0)) if c["kind"] == "onset"
                                  else ((value[:-1] == 0) & (value[1:] > 100))) + 1
        assert len(switches) == 1, f"Ambiguous source switch: {c['event_id']}"
        i = switches[0]
        before, after = raw.iloc[i - 1], raw.iloc[i]
        if c["expected_after"]:
            assert before.raw_timestamp == c["expected_before"] and after.raw_timestamp == c["expected_after"]
        gap = (after.ts - before.ts).total_seconds()
        assert 0 < gap <= 30, "Missing-data boundary cannot establish a precise switch"
        rows.append({**{k: v for k, v in c.items() if k != "candidate"},
                     "candidate_utc": c["candidate"].isoformat(),
                     "last_before_utc": before.ts.isoformat(), "first_after_utc": after.ts.isoformat(),
                     "before_kw": before.value, "after_kw": after.value,
                     "raw_gap_s": gap, "verified_from_original_raw": True,
                     "meaning": "first observed changed sample; physical change time not established"})
        write(raw.drop(columns="ts"), f"event_verification_m{c['month']:02d}.csv")
        print(c["event_id"], before.raw_timestamp, "->", after.raw_timestamp, flush=True)
    write(pd.DataFrame(rows), "verified_events.csv")


def load_minutes(month, usecols=None):
    d = pd.read_csv(ROOT / f"outputs/task3/data/minute_2024_{month:02d}.csv.gz", usecols=usecols)
    d.index = pd.to_datetime(d.window_end_utc, utc=True)
    assert d.index.is_unique and d.index.is_monotonic_increasing
    return d


def windows():
    events_df = pd.read_csv(OUT / "verified_events.csv")
    assert events_df.verified_from_original_raw.all()
    early = pd.concat([load_minutes(m, ["window_end_utc"] + MATCH) for m in [1, 2, 3]])
    eligible = early[MATCH].notna().all(axis=1) & early.STW_kn.ge(3)
    scale = early.loc[eligible, MATCH].quantile(.75) - early.loc[eligible, MATCH].quantile(.25)
    assert scale.gt(0).all()
    write(scale.rename("jan_mar_iqr").rename_axis("channel").reset_index(), "matching_scales.csv")
    all_windows, coverage = [], []
    for e in events_df.itertuples():
        d = load_minutes(e.month)
        t0 = pd.Timestamp(e.first_after_utc)
        pre = d[(d.index > t0.floor("min") - HALF) & (d.index <= t0.floor("min"))]
        assert len(pre) == 10 and pre[MATCH].notna().all().all()
        event_x = pre[MATCH].median()
        all_windows.append({"event_id": e.event_id, "window_id": e.event_id, "role": "event",
                            "state": e.kind, "month": e.month, "anchor_utc": t0.isoformat(),
                            "rms_distance": 0., "max_feature_distance": 0.})
        hourly = pd.date_range(d.index.min().floor("D"), d.index.max().floor("D"), freq="h")
        hourly = hourly + (t0 - t0.floor("h"))
        candidates = []
        for anchor in hourly:
            if abs(anchor - t0) < pd.Timedelta(hours=24):
                continue
            before = d[(d.index > anchor.floor("min") - HALF) & (d.index <= anchor.floor("min"))]
            enclosing = d[(d.index > (anchor - HALF).floor("min")) & (d.index <= (anchor + HALF).ceil("min"))]
            if len(before) != 10 or len(enclosing) != 21 or not before[MATCH].notna().all().all():
                continue
            observed = enclosing.target_n.gt(0) & enclosing.STW_kn.ge(3) & enclosing[TARGET].notna()
            if not observed.all():
                continue
            if enclosing.target_min.gt(0).all() and enclosing.target_negative_n.eq(0).all():
                state = "positive_control"
            elif enclosing[TARGET].eq(0).all() and enclosing.target_negative_n.eq(0).all():
                state = "zero_control"
            else:
                continue
            delta = (before[MATCH].median() - event_x) / scale
            rms, max_delta = float(np.sqrt(np.mean(delta**2))), float(delta.abs().max())
            candidates.append({"event_id": e.event_id, "state": state, "month": e.month,
                               "anchor_utc": anchor.isoformat(), "rms_distance": rms,
                               "max_feature_distance": max_delta})
        cand = pd.DataFrame(candidates)
        for state in ["positive_control", "zero_control"]:
            pool = cand[cand.state.eq(state)].copy() if len(cand) else cand
            supported = pool[(pool.rms_distance <= .5) & (pool.max_feature_distance <= 1)] if len(pool) else pool
            selected = supported.sort_values(["rms_distance", "anchor_utc"]).head(24) if len(supported) else supported
            coverage.append({"event_id": e.event_id, "control_state": state, "candidate_n": len(pool),
                             "supported_n": len(supported), "selected_n": len(selected),
                             "adequate_for_repeatability_screen": len(selected) >= 12})
            for j, rec in enumerate(selected.to_dict("records"), 1):
                all_windows.append({**rec, "window_id": f"{e.event_id}_{state}_{j:02d}", "role": "control"})
        print(e.event_id, "matched controls", coverage[-2:], flush=True)
    w = pd.DataFrame(all_windows)
    write(w, "matched_windows.csv")
    write(pd.DataFrame(coverage), "matching_coverage.csv")
    # All anchors are fixed before raw independent signatures are inspected.
    for month, group in w.groupby("month"):
        prefixes = set()
        for anchor in group.anchor_utc:
            a = pd.Timestamp(anchor)
            prefixes |= prefixes_between(a - HALF, a + HALF)
        raw = stream_selected(month, prefixes, INDEPENDENT + [TARGET])
        write(raw.drop(columns="ts"), f"raw_windows_m{month:02d}.csv")
        print("Extracted", month, len(raw), "raw rows", flush=True)


def shortest_angle(value):
    return (value + 180.) % 360. - 180.


def signature(s, anchor, channel):
    s = s[(s.ts >= anchor - HALF) & (s.ts < anchor + HALF)].sort_values("ts")
    values = s.value.to_numpy(float)
    if channel in ANGLE_COLUMNS:
        values = np.rad2deg(np.unwrap(np.deg2rad(values)))
    before = (s.ts < anchor).to_numpy()
    groups = []
    for take in [before, ~before]:
        g = s.loc[take]
        v = values[take]
        # Pandas can infer datetime64[us]; integer conversion preserves that
        # unit. Normalize explicitly before treating integers as nanoseconds.
        ts_ns = g.ts.dt.as_unit("ns").astype("int64").to_numpy()
        intervals = np.diff(ts_ns) / 1e9
        if len(intervals):
            assert np.allclose(intervals, g.ts.diff().dropna().dt.total_seconds().to_numpy(),
                               rtol=0, atol=1e-9), "Timestamp units disagree with timedelta reference"
        # Offset from nearest regular 15-second epoch tick; no target-clock join.
        phase = ((ts_ns % 15_000_000_000 + 7_500_000_000) % 15_000_000_000 - 7_500_000_000) / 1e9
        vframe = pd.DataFrame({"value": v, "minute": g.ts.dt.floor("min").to_numpy()})
        within = vframe.groupby("minute").value.agg(["count", "std"])
        within = within[within["count"].ge(4)]
        groups.append({"n": len(v), "median": float(np.median(v)) if len(v) else np.nan,
                       "sd": float(np.std(v, ddof=1)) if len(v) > 1 else np.nan,
                       "within": float(within["std"].median()) if len(within) else np.nan,
                       "cadence": float(np.median(intervals)) if len(intervals) else np.nan,
                       "max_gap": float(np.max(intervals)) if len(intervals) else np.nan,
                       "phase": float(np.median(phase)) if len(phase) else np.nan,
                       "first": float(v[0]) if len(v) else np.nan,
                       "last": float(v[-1]) if len(v) else np.nan})
    b, a = groups
    level, edge = a["median"] - b["median"], a["first"] - b["last"]
    if channel in ANGLE_COLUMNS:
        level, edge = shortest_angle(level), shortest_angle(edge)
    return {"n_before": b["n"], "n_after": a["n"], "median_before": b["median"],
            "median_after": a["median"], "level_delta": level, "edge_delta": edge,
            "sd_delta": a["sd"] - b["sd"], "within_minute_sd_delta": a["within"] - b["within"],
            "cadence_delta_s": a["cadence"] - b["cadence"], "max_gap_delta_s": a["max_gap"] - b["max_gap"],
            "phase_delta_s": a["phase"] - b["phase"], "count_delta": a["n"] - b["n"]}


def analyse():
    w = pd.read_csv(OUT / "matched_windows.csv")
    signatures, checks, states = [], [], []
    for month, group in w.groupby("month"):
        raw = pd.read_csv(OUT / f"raw_windows_m{month:02d}.csv")
        raw["ts"] = pd.to_datetime(raw.raw_timestamp, utc=True)
        duplicate_n = int(raw.duplicated(["ts", "qid"]).sum())
        assert duplicate_n == 0
        d = load_minutes(month)
        # Extraction selected complete raw-minute prefixes, allowing exact replay.
        raw["window_end"] = raw.ts.dt.floor("min") + MINUTE
        for (end, channel), g in raw.groupby(["window_end", "channel"]):
            source = d.loc[end]
            v = g.value.to_numpy(float)
            if channel in ANGLE_COLUMNS:
                angle = np.arctan2(np.sin(np.deg2rad(v)).mean(), np.cos(np.deg2rad(v)).mean())
                rebuilt = np.rad2deg(angle) % 360.
                diff = abs(shortest_angle(rebuilt - source[channel]))
            else:
                rebuilt = float(v.mean())
                diff = abs(rebuilt - source[channel])
            count_col = "target_n" if channel == TARGET else "n__" + channel
            tolerance = max(.00002, abs(rebuilt) * .000006)
            checks.append({"month": month, "window_end_utc": end.isoformat(), "channel": channel,
                           "raw_n": len(v), "compact_n": int(source[count_col]),
                           "raw_mean_or_circular_mean": rebuilt, "compact_value": source[channel],
                           "abs_difference": diff, "serialization_tolerance": tolerance,
                           "pass": len(v) == source[count_col] and diff <= tolerance,
                           "canonical_duplicate_n": duplicate_n})
        for row in group.itertuples():
            anchor = pd.Timestamp(row.anchor_utc)
            power = raw[(raw.channel == TARGET) & (raw.ts >= anchor - HALF) & (raw.ts < anchor + HALF)]
            states.append({"window_id": row.window_id, "role": row.role, "state": row.state,
                           "raw_target_n": len(power), "raw_zero_n": int(power.value.eq(0).sum()),
                           "raw_negative_n": int(power.value.lt(0).sum()),
                           "raw_positive_n": int(power.value.gt(0).sum()),
                           "control_state_verified": row.role == "event" or
                           (power.value.gt(0).all() if row.state == "positive_control" else power.value.eq(0).all())})
            for channel in INDEPENDENT:
                signatures.append({"event_id": row.event_id, "window_id": row.window_id,
                                   "role": row.role, "state": row.state, "channel": channel,
                                   **signature(raw[raw.channel == channel], anchor, channel)})
    sig = pd.DataFrame(signatures)
    check = pd.DataFrame(checks)
    write(sig, "independent_signatures.csv")
    write(check, "raw_minute_checks.csv")
    write(pd.DataFrame(states), "raw_window_coverage.csv")
    comparisons = []
    for (event, channel), group in sig.groupby(["event_id", "channel"]):
        ev = group[group.role == "event"].iloc[0]
        for state in ["positive_control", "zero_control"]:
            controls = group[group.state == state]
            for stat in STATISTICS:
                v = controls[stat].dropna().to_numpy(float)
                value = float(ev[stat])
                lo, hi = (float(v.min()), float(v.max())) if len(v) else (np.nan, np.nan)
                outside = (value < lo) or (value > hi)
                comparisons.append({"event_id": event, "channel": channel, "statistic": stat,
                                    "control_state": state, "control_n": len(v), "event_value": value,
                                    "control_min": lo, "control_median": float(np.median(v)) if len(v) else np.nan,
                                    "control_max": hi, "outside_matched_range": outside,
                                    "adequate_samples": ev.n_before >= 30 and ev.n_after >= 30,
                                    "direction": int(np.sign(value)) if np.isfinite(value) else 0})
    comp = pd.DataFrame(comparisons)
    write(comp, "matched_signature_comparisons.csv")
    repeat = []
    for (channel, stat), group in comp[comp.control_state == "positive_control"].groupby(["channel", "statistic"]):
        g = group.set_index("event_id")
        assert set(g.index) == {"m06_onset", "m08_onset", "m09_recovery"}
        adequate = bool((g.control_n >= 12).all() and g.adequate_samples.all())
        onset_direction = g.loc["m06_onset", "direction"]
        coherent = onset_direction != 0 and onset_direction == g.loc["m08_onset", "direction"] and onset_direction == -g.loc["m09_recovery", "direction"]
        repeat.append({"channel": channel, "statistic": stat, "adequate_controls_and_samples": adequate,
                       "outside_range_all_events": bool(g.outside_matched_range.all()),
                       "same_onset_opposite_recovery_direction": bool(coherent),
                       "repeatability_screen_pass": bool(adequate and coherent and g.outside_matched_range.all())})
    write(pd.DataFrame(repeat), "repeatability_screen.csv")
    print("Raw/minute checks", len(check), "failed", int((~check["pass"]).sum()), flush=True)
    print("Repeatability screens passed", sum(r["repeatability_screen_pass"] for r in repeat), flush=True)


def finish():
    baseline = pd.read_csv(OUT / "original_artifact_hashes.csv")
    preserved = []
    for row in baseline.itertuples():
        path = ROOT / row.path
        after = digest(path) if path.exists() else "MISSING"
        preserved.append({"path": row.path, "sha256_before": row.sha256_before,
                          "sha256_after": after, "unchanged": after == row.sha256_before})
    preserve = pd.DataFrame(preserved)
    write(preserve, "artifact_preservation.csv")
    manifest = json.loads((OUT / "audit_manifest.json").read_text())
    checks = pd.read_csv(OUT / "raw_minute_checks.csv")
    coverage = pd.read_csv(OUT / "raw_window_coverage.csv")
    signatures = pd.read_csv(OUT / "independent_signatures.csv")
    events_df = pd.read_csv(OUT / "verified_events.csv")
    frozen_hash = manifest["script_sha256"]
    current_hash = digest(Path(__file__))
    revision_file = OUT / "implementation_revision.json"
    revision = json.loads(revision_file.read_text()) if revision_file.exists() else {}
    script_verified = current_hash == frozen_hash or (
        revision.get("frozen_script_sha256") == frozen_hash and
        revision.get("corrected_script_sha256") == current_hash and
        revision.get("protocol_or_control_selection_changed") is False)
    qa = [
        ("Original artifacts unchanged", bool(preserve.unchanged.all()), f"{len(preserve)} SHA256 comparisons"),
        ("Frozen protocol and implementation revision accounted for", script_verified,
         "Explicit datetime-unit correction documented; no protocol, event or control change"),
        ("Timing arithmetic independently checked", True,
         "Every corrected interval agrees with pandas timedelta.total_seconds to 1e-9 s during analysis"),
        ("Exact event samples verified", bool(events_df.verified_from_original_raw.all()), "Source power sampled before independent windows selected"),
        ("Only permitted independent signatures", set(signatures.channel) == set(INDEPENDENT), "No torquemeter/target fields in signal statistics"),
        ("Raw minute replay", bool(checks["pass"].all()), f"{len(checks)} channel-minute comparisons"),
        ("Canonical duplicates absent in selected extracts", bool(checks.canonical_duplicate_n.eq(0).all()), "Parsed UTC timestamp plus exact QID"),
        ("Retrospective controls verified in raw", bool(coverage.control_state_verified.all()), "Diagnostic control sampling only"),
        ("All candidate events retained", len(events_df) == 3 and signatures[signatures.role == "event"].event_id.nunique() == 3, "Two onsets and one recovery"),
    ]
    write(pd.DataFrame([{"check": c, "status": "PASS" if ok else "FAIL", "evidence": evidence} for c, ok, evidence in qa]), "audit_qa.csv")
    assert all(ok for _, ok, _ in qa), "Audit QA failure must be investigated; no automatic scientific decision"
    write_json({"completed_computation": True, "decision": "pending evidence review; no automatic model work",
                "original_artifacts_verified": len(preserve)}, "completed.json")
    print("Audit computations complete; originals unchanged; review evidence before final decision", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "events", "windows", "analyse", "finish"])
    args = parser.parse_args()
    globals()[args.stage]()
