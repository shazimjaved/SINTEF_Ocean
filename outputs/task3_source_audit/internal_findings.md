# Internal bounded source and transition audit

**Final decision: C. No decisive new evidence; stop model exploration.**

The audit establishes neither a new source/processing defect in V1-V8 nor a
repeatable independent transition signal. It does not prove that the original
recordings are physically valid or that transition identification is impossible.
No model, classifier, corrected target, relabelling or V9 was created.

## Scope and preservation

The protocol was written before raw transition verification and control
selection. Only raw June, August and September were analysed. January-March
independent minute features supplied matching scales without target filtering.
July, November and December were not evaluated; their bytes were included only
in the preservation hashes. Existing models and predictions were not rerun.

All **718 original artifacts** retain identical SHA256 hashes. The final audit
QA has **9 PASS, 0 FAIL**. This validates the enumerated checks, not physical
measurement accuracy. No data were uploaded or messages sent externally.

## Exact event verification

June and August candidates came from V3's raw mechanical-switch manifest, not
from assumed dates. September's recovery candidate came from V2's episode
manifest; raw power resolved its first positive sample before independent
windows were selected. Each pair was verified in its original monthly CSV.

| Event | Last preceding sample, UTC | First changed sample, UTC | Power before -> after, kW |
|---|---|---|---|
| June onset | 2024-06-10 10:40:30.003 | 2024-06-10 10:40:45.003 | 5640.773926 -> 0 |
| August onset | 2024-08-27 20:01:15.006 | 2024-08-27 20:01:30.007 | 3214.619629 -> 0 |
| September recovery | 2024-09-11 10:18:00.037 | 2024-09-11 10:18:15.015 | 0 -> 5096.359375 |

These are first observed changed samples, bounding a recorded transition across
approximately 15 seconds. They are not exact physical-state change times. The
underway-zero episode ends at June 18 and September 10 were not substituted for
recoveries: the existing manifests identify speed-threshold boundaries while
power remains zero. See `verified_events.csv` and `event_verification_*.csv`.

## Source provenance

Slide 6 of the original challenge presentation announces that four-fifths of
the dataset will be raw data and designated periods will contain extra
challenges. The SINTEF brief mentions torque miscalibration; the announcement
and brief refer to cleaning/event information. These are retained as source
statements, without attributing a modification to this release or any interval.

The project inventory and metadata search found no release-specific alteration
manifest, applicable quality/event log, or original replacement truth. Absence
of such material proves neither that modifications occurred nor that they did
not. The existing torque-scale and reference-engine ambiguities remain
unresolved; they are not new calibration discoveries.

The August 28-31 Noon records report propulsion consumption 21.4, 21.7, 21.5
and 21.6 during dates previously identified as recorded-zero forward-power
days. Units, reporting interval and measurement independence remain unverified.
These entries provide contradictory context to investigate, not power labels
or permission to relabel zeros. See `source_evidence.csv`,
`metadata_search_hits.csv`, `source_inventory.csv`, `noon_context.csv` and
`missing_metadata.csv`.

## Raw processing checks

The extracted 55,160 rows cover three event windows and 54 matched control
windows, plus enclosing complete-minute context. The independent replay checks
**13,793 channel-minute groups** across power and ten independent sensors.
All observed counts and arithmetic/circular means agree with the existing
minute tables within their six-significant-digit serialization tolerance.
Maximum target difference is **0.0052245 kW**. No duplicate canonical UTC
timestamp/QID pair was found in these extracts.

This is a selected-window check, not a new full-year raw-data certification.
Nothing here establishes physical synchronization or real delivery latency.

## Independent timing and variability

Controls were fixed before raw signature inspection. Matching used only
pre-anchor medians of STW, SOG, CAMS RPM, fuel load, scavenging pressure and
turbocharger RPM. Scales came from complete Jan-March independent observations.
Same-month hourly candidates were at least 24 hours from the event, using
normalized RMS distance <=0.5 and maximum individual distance <=1. Up to 24
controls per state were retained without relaxing calipers after results.

| Event | Supported positive candidates / selected | Supported zero candidates / selected |
|---|---:|---:|
| June onset | 72 / 24 | 35 / 24 |
| August onset | 2 / 2 | 4 / 4 |
| September recovery | 0 / 0 | 0 / 0 |

Positive controls are ordinary recorded-positive operation; zero controls are
stable recorded-zero intervals, not certified physical zero operation. Target
values selected events and control states retrospectively only. Controls can
occur before or after an event, so these are diagnostic comparisons, not
chronological predictive validation or estimates of deployment false alarms.

Ten independent channels were compared using eight fixed contrasts: level,
adjacent-sample jump, raw standard deviation, within-minute standard deviation,
median cadence, maximum sample gap, timestamp phase and count changes.
No torquemeter channel supplied a candidate detection signature.

Corrected event timestamp-phase changes range from -6 to +4.5 milliseconds;
all event median-cadence contrasts are zero. June has six channel/statistic
contrasts beyond its 24 positive-control ranges, including turbocharger
within-minute variability. That variability rises by 20.336 RPM in June and
14.873 RPM in August and falls by 9.687 RPM at September recovery. This is an
exploratory pattern, not decisive evidence: August has just two positive
controls and September has none under the frozen matching rule. Ordinary
operating variability and multiple comparisons remain plausible explanations.

The predeclared repeatability screen required >=12 positive controls at each
event, adequate raw samples, consistent signed onset changes, opposite recovery
change, and an effect outside all matched ranges. **No contrast has adequate
control support across all three events.** Consequently, zero passing screens
must not be presented as proof that an independent signal is absent.
All events and unsupported comparisons remain in the CSVs; no events or failed
matches were replaced. See `matching_coverage.csv`, `matched_windows.csv`,
`independent_signatures.csv`, `matched_signature_comparisons.csv` and
`repeatability_screen.csv`.

## Audit implementation correction

The initial new timing calculation converted pandas datetime64[us] integers
as though they were nanoseconds. A direct timedelta check identified this
audit-only bug. Explicit nanosecond normalization corrected cadence/phase
statistics; the original feature pipeline already normalizes nanoseconds.
Every corrected interval was checked against timedelta.total_seconds.

Initial analysis files are retained as `*_initial.csv` and excluded from
conclusions. All non-timing signatures are identical before and after the fix;
event anchors, controls, matching scales and decision rules did not change.
`implementation_revision.json` links the frozen and corrected code hashes.
This correction is not evidence of a V1-V8 or source-data defect.

## Reproduction and stop

From the project root run the audit script with stages `prepare`, `events`,
`windows`, `analyse`, `finish`, in that order, using `python -X utf8 -B`.
Completed outputs refuse overwriting. For an independent reproduction, use a
separate project copy retaining original inputs but without this audit's
outputs. Python, pandas and numpy versions are recorded in the manifest;
PyMuPDF is also required for source extraction. No model packages are called.

`completed.json` records computational completion before evidence review;
`audit_decision.json` records the final reviewed decision. The bounded audit is
finished. No matching-rule changes, new fits or further exploration follow.

**C. No decisive new evidence; stop model exploration.**
