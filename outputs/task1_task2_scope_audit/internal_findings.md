# Internal scope audit: Task 1 and Task 2

Audit date: 30 October 2026. Project root: `C:\Users\GOGI LAPTOP\Downloads\SINTEF_Ocean_Project`.

**Finding:** The delivered reports align with the challenge's shaft-power estimation and data-quality objectives, but do not express its clean-versus-current performance comparison and cleaning-decision objectives. The teammate's concern is supported by the original sources. Task 1 is predominantly a technical study specification. Task 2 provides useful sensor understanding, but leaves the evidence needed for a cleaning-related interpretation undocumented.

**Cleaning-event records: not found in the inspected package.** This is a bounded finding about the inspected files, archives and metadata, not a claim that records do not exist elsewhere. Engineering reference data are present, including a towing-tank report explicitly describing clean-bottom predictions. Those references do not establish a dated clean operating period for the supplied sensor observations.

## Review authority, boundaries and evidence notation

The delivered reports are the PDFs identified by the user during this review: `Task 1 Report.pdf` (2 pages), `Task 2 Report.pdf` (7 pages), and supporting `Scientific_Validation.pdf` (2 pages), all dated 25 October 2026. The related Markdown documents under `outputs/reports/` were also read. The change plan below follows the **delivered PDF section titles**, not merely the Markdown titles. An exact PDF build chain was not established; report-authoring LaTeX/Word sources were not found in the inspected scope.

No existing source or deliverable was edited, replaced, renamed or deleted. Only the two audit artifacts in this directory were written. No model was trained, no Task 3 results, metrics or artifacts were opened, and no V1–V8 investigation was reviewed. The original `Big Data from ships Challenge V1.pptx` is an authorized challenge source, not a Task 3 investigation. Proposed methods mentioned inside the delivered Task 1/2 reports were read only to assess section placement. The professor's pending Task 3 reply remains outside this review.

Evidence labels used below:

- **Verified:** directly observed document content, file listing, archive directory, metadata or a stated check of the small Noon CSVs.
- **Existing report evidence:** an observation already reported in Task 1/2 or inventory tables; its large sensor-data computation was not rerun here.
- **Missing evidence:** an absent record, undocumented relationship or unanswered provenance question within this inspection.
- **Recommendation:** a proposed report correction or request; not an achieved analysis result.

All paths below are relative to the project root unless stated otherwise. `source_inventory.csv` records exact absolute paths, inspection methods, evidence locators, limitations, sizes and timestamps. It contains 50 inspected source-file entries, 127 Office archive-member entries, and supporting metadata/search records. Small source files have SHA-256 fingerprints; the large raw CSVs were inspected through file/header and existing inventory metadata, not exhaustively rescanned. File and document timestamps are not cleaning dates or proof of when a source was originally supplied.

| Evidence ID | Exact source path | Main locators |
|---|---|---|
| CH01 | `docs/challenge/HullPIC25 Announcement.pdf` | PDF pp. 1–3, printed pp. 117–119: context, promised data, challenge tasks and scoring |
| CH02 | `docs/challenge/Big Data from ships Challenge V1.pptx` | Slides 3–9: challenges, sources, outputs and comparison; slide 13: future challenges |
| CH03 | `docs/SINTEF_Ocean_v2.pdf` | PDF pp. 3, 5–7, 10–13; p. 13 has printed slide number 14 |
| CH04 | `docs/2026_Lecture2_Dataset.pdf` | PDF pp. 7–9: Task 1/2 criteria and suggested report structure |
| T1 | `Task 1 Report.pdf` | §1–3 on p. 1, continuing §3 and §4–6 on p. 2 |
| T2 | `Task 2 Report.pdf` | §1–2 p. 1; §2.1–3 pp. 2–4; §4 pp. 5–6; §5–6 p. 7 |
| VAL01 | `Scientific_Validation.pdf` | Both pages, especially §1 scope and §5–6 limitations/conclusion |
| R01 / R02 | `outputs/reports/task1_preliminary.md`; `outputs/reports/task2_preliminary.md` | Related editable drafts, six main sections each |
| VAL02 | `outputs/reports/scientific_validation_report.md` | Supporting validation/correction record and unresolved questions |
| REF01 | `docs/Metrics registration - Google Sheets.pdf` | Both pages: registered quantities and sources |
| REF02 | `docs/Vessel/Particulars.xlsx` | `Sheet1`, populated cells B3:F80 |
| REF03 | `docs/Vessel/Sea_Trials_curves.jpg` | Complete speed–power chart, inspected visually |
| REF04 | `docs/Vessel/TOWING TANK MODEL TEST REPORT for A 76000DWT Bulk Carrier with&without PSV.pdf` | PDF pp. 2, 6–8 and 10–14, especially p. 12 (printed p. 11) |

## 1. Business objectives explicitly specified by the challenge

The original announcement and the SINTEF course presentation should be distinguished: the announcement specifies comparative challenge outputs; the SINTEF presentation connects performance analysis directly to operational decisions.

| Objective | Explicit source evidence | Business interpretation and scope |
|---|---|---|
| Compare clean and current vessel performance | CH01 p. 3 task 1: clean and latest-condition speed–power curves for different drafts; CH02 slides 3 and 7 | Establish a reference for interpreting deterioration while accounting for loading condition. |
| Estimate performance loss potentially associated with fouling | CH01 p. 3 task 2: added power and/or speed loss; CH02 slide 7 | Express deterioration in operationally interpretable terms. This objective does not make any observed excess proof of fouling. |
| Support hull/propeller cleaning decisions | CH03 p. 13 explicitly asks whether performance indicates that the hull and/or propeller should be cleaned, and additionally whether cleaning is worthwhile; CH01 p. 1 identifies timely hull cleaning among shipowner needs | Support the shipowner/performance team's maintenance decision. Economic worth requires additional cost and benefit evidence. |
| Understand trip energy performance and weather-sensitive speed choices | CH03 p. 13 asks about good/bad trips considering weather and speed recommendations to reduce trip power; pp. 3 and 5–7 motivate operational efficiency and explain influences | Improve energy-related operating decisions. No numerical benefit is promised by the source. |
| Estimate shaft power and fill missing performance information | CH01 p. 3 task 3: estimate power and/or consumption in missing periods where possible; CH03 p. 13: robust shaft-power prediction as an input to route optimization | Power estimation is a legitimate enabling objective. It is one part of the wider performance problem. |
| Produce trustworthy analysis despite imperfect data | CH01 p. 3 task 6: data quality/uncertainty; CH02 slides 3, 7 and 9; CH03 pp. 2, 4 and 13 | Prevent decisions being driven by sensor problems, gaps or unjustified confidence. |
| Compare methods transparently | CH01 pp. 1–3; CH02 slides 7–10 | Benchmark vendors/methods and improve decision-support tools; encourage reproducibility and shared learning. |
| Optionally separate hull from propeller fouling | CH01 p. 3 task 5 explicitly makes this optional | Do not silently turn this into a mandatory or already feasible attribution task. |

CH01 p. 2 also lists workshop/community aims concerning collaboration, research capacity, open science, innovation, learning, ethical use, resources, policy/sustainability, recognition, accessibility and feedback. These contextual aims need not all become this project's business KPIs. Similarly, broader generalization across vessels/types is discussed as future challenge work (CH01 p. 2; CH02 slide 13), not something this single-vessel project must demonstrate now.

The course rubric supports the teammate's section-placement point: Task 1 should establish context, stakeholders, the decision, success criteria and constraints; Task 2 should establish background, sources, relevant variables, data quality and limitations. Detailed methods and technical evaluation belong later (CH04 pp. 7–9).

## 2. What Task 1 currently expresses, omits or places too technically

| Delivered Task 1 evidence | Assessment |
|---|---|
| §1, p. 1: estimate shaft mechanical power using operating/environmental measurements from other sources; provide a secondary indication or plausibility check | **Present and valid, but narrower than the challenge.** It supports the power-estimation strand. The added torquemeter-plausibility use is a proposed project use, not the central cleaning decision explicitly asked by SINTEF. |
| §1 and §5: performance-monitoring usefulness depends on accuracy/availability; route and fuel benefits remain unproven | **Appropriate caution.** Fuel/routing are secondary or deferred, but cleaning and condition comparison are not stated as the business destination. |
| No clean/current-condition baseline objective, added-power/speed-loss objective, or cleaning decision in either page | **Missing central objectives.** The simple regression baselines in §5 are technical comparators; they are not identified clean-condition speed–power references. |
| §3: target anomalies, coverage, repeated weather and representativeness; §6: timing and reliability dependencies | **Well represented data-quality concern**, with useful restrictions on interpretation. The detailed counts and processing implications dominate a business section. |
| §5 mentions stakeholder-defined error requirements, without identifying users or a concrete maintenance decision | **Partial stakeholder/success framing.** Decision owner, review action and business measures are unspecified. Technical improvement over a baseline alone does not define usefulness for maintenance. |
| §1: supervised regression, completed-minute aggregation and target QID; §2: 36-channel accounting, 24 candidates, exclusions and circular processing | **Too technical for the main business narrative.** Relevant facts should remain traceable in Task 2 or later methods, with only high-level data limitations retained in Task 1. |
| §4: month-by-month development/test allocation; §5: MAE/RMSE/R² and technical baselines | **Later methods/evaluation material.** This audit recommends relocating the specification, not changing or endorsing the pending Task 3 work. |

**Recommendation:** Make the primary decision the identification and review of possible excess propulsion demand against an appropriate expected-performance reference, to inform whether hull/propeller inspection or cleaning merits consideration. Retain shaft-power estimation as an enabling capability and separate missing-value reconstruction from a clean-condition reference. Keep fuel reduction, cleaning worth and routing as conditional downstream uses.

A model that reproduces observed power is not automatically a clean-condition model: its reference observations may already reflect degradation or sensor bias. Accurate power reconstruction and credible clean/current comparison are separate evidence requirements. This is a requirement clarification, not a finding about any Task 3 model.

## 3. Cleaning-event availability: search scope and exact evidence

**Verified result: actual hull/propeller cleaning-event records were not found in the inspected package.** The following checks support that conclusion.

| Inspected location/container | Evidence obtained | Availability implication |
|---|---|---|
| `data/raw/` | Exactly `1.csv` through `12.csv` and `Jan25.csv`. First-line/schema checks plus `outputs/tables/data_inventory.csv`, `qid_per_file.csv`, `qid_reconciliation.csv` and `data_dictionary.csv`; registration checked in REF01. | Sensor measurement files. The registered/present channel metadata contains no cleaning-event quantity; the three-field 2024 schema is timestamp/QID/value. No separate event sidecar was listed. Full raw numeric contents were not searched again. |
| `data/Noon Reports/` | All 12 CSVs inspected: 366 unique daily dates, 15 common fields. Every field value checked for `clean`, `foul`, `maintenance`, `dry.?dock`, `polish`, `coating`, `event`; zero matches. Exact filenames and monthly date bounds are individual CSV inventory entries NOON01–NOON12. | No cleaning-event field or cleaning-related entry in these supplied Noon CSVs. These are daily operational summaries, not maintenance records. |
| `docs/` | All 12 file names inventoried, including hidden/ignored files: 5 PDFs, 2 JPEGs, 2 CSV templates, PPTX, DOCX, XLSX. | References and examples are present; no standalone event log or engine shop-test dataset/report was identified. |
| `docs/challenge/Big Data from ships Challenge V1.pptx` | All 107 ZIP member names, slide/notes text and relevant relationships inspected. Slides 4–5 contain particulars, sea-trial material and model photographs; slide 6 lists cleaning events. No event-file or embedded-object candidate in the archive listing. | The presentation advertises cleaning events; it does not contain a located event dataset. |
| `docs/Vessel/Particulars.xlsx` | All nonempty worksheet cells and all 11 ZIP member names inspected. One sheet contains dimensions/loading conditions, engine and propeller particulars. | No cleaning chronology or maintenance table. |
| `docs/challenge/Code of Conduct.docx` | Document text and all 9 ZIP member names inspected. | Source-use terms, not maintenance data. |
| Five source PDFs under `docs/`, plus the three user-identified report PDFs | PDF embedded-attachment name collections were empty. Relevant source/report text inspected. | No attached event file found. Document creation dates are not event dates. |
| Permitted workspace filename search, with Task 3/investigation trees pruned | No standalone `.zip`, `.7z`, `.rar`, `.tar`, `.gz`, `.bz2`, `.xz`, `.tgz`, `.tbz` or `.cab` archive found. Office archives above were listed directly, without extraction. | No additional dataset archive was available to inspect within this scope. No claim is made about excluded trees or locations outside the project. |

The event/reference filename search used cleaning/fouling/maintenance/dry-dock/polishing/coating/event/shop-test/sea-trial terms. It located `docs/Templetes/BillTsars_Model1_CleanBaselineScantling.csv` and `docs/Vessel/Sea_Trials_curves.jpg`, neither of which is an actual cleaning-event record. The complete data/document file listings and Office member paths are retained in `source_inventory.csv`.

Two particularly important false positives are:

- `docs/Templetes/BillTsars_Model1_CleanBaselineScantling.csv`: 45 speed rows from 5 to 16 kn, with every power value 100000 and every RPM value 100.1. This is a supplied output-layout example, not validated clean-condition measurements.
- `docs/Templetes/BillTsars_Model1_Timeseries.csv`: contains `Power Expected`, fouling/uncertainty columns and `clean`, with 22 repeated example-value rows dated 9 December 2024, 10:30–10:51, followed by empty rows. A `clean=TRUE` example flag supplies no cleaning action, event provenance or maintenance history. **9 December must not be inferred to be a cleaning date.**

CH01 p. 2, CH02 slide 6 and CH03 p. 10 say cleaning events are supplied or planned. That is evidence of intended source provision, not proof of local availability. There is also no verified date for the last cleaning before 2024, no dated clean operating interval, and no known event coverage/completeness in this inspection.

## 4. Supplied sources that could support clean/current comparisons

| Source and verified content | Potential use | Suitability limits to document |
|---|---|---|
| REF04 towing-tank report: four loading conditions, with/without PSV; delivered propeller power and RPM; p. 12 explicitly assumes calm sea, sufficient depth and clean bottom | Engineering clean-condition reference. This is the clearest located statement of clean-reference assumptions. | These are model-test/full-scale predictions, not proof of a clean sensor-data period. Select the applicable PSV configuration, draft/trim and speed range; reconcile sea margins, corrections and delivered propeller power with the measured shaft-power location. With/without-PSV savings columns are **not cleaning savings**. |
| REF03 sea-trial chart: model and measured curves at design draft and ballast, axes `Pd(kW)` and `Vs(kn)` | Independent candidate speed–power reference and cross-check | Image only; trial date, full conditions, cleanliness, correction procedure and numeric source table are not established. Its annotations use 8833 and 0.985; REF04 p. 8 gives a 9500 kW engine rating and 0.99 transmission efficiency. Their relationship needs explanation; this observation does not prove a vessel mismatch. |
| REF02 particulars: design 12.20/12.20 m, scantling 14.25/14.25 m, ballast 5.00/7.80 m and heavy-ballast 4.40/9.40 m fore/aft drafts; wetted areas, displacement volumes, engine/propeller data | Identify relevant reference loading/configuration and physical background | These are reference conditions, not daily observed loading. The workbook labels displacement as volume in m³; Noon `Displacement` has no unit in its column heading. Do not equate them without confirming units and any density conversion. |
| `data/raw/1.csv`–`12.csv`; REF01 and existing inventory/QID tables | Observed 2024 power, speed through water/over ground, heading/turning, engine and environmental context for current-condition comparisons | Existing Task 2 evidence documents suspect power, all-zero draft sensors, uneven coverage, repeated provider data and uncertain timing. Conditions must be comparable; a pooled speed–power relation alone cannot identify fouling. No clean/current labels were located. |
| `data/raw/Jan25.csv` | Later motion/environmental context | Existing QID metadata shows no torquemeter/shaft-power target. It cannot directly establish a measured January 2025 speed–power curve. Confirm timezone/aggregation semantics. “Current” must identify a usable dated window, not simply the latest filename. |
| Twelve files under `data/Noon Reports/` | Daily loading context: forward/mid/aft draft and displacement; possible trim information after definition checks; weather/sea-state and coarse propulsion consumption | All 366 dates have populated draft/displacement fields, but daily timing, units and within-day representativeness remain unconfirmed. No direct shaft-power/speed pair or cleaning field. A lag suitable for online availability is not automatically the best representation of loading during a retrospective comparison. |
| Challenge CSV templates | Document expected curve/result layout and uncertainty/condition flags | Templates support reporting, not empirical identification of clean state or cleaning effectiveness. |

**Shop-test distinction:** CH01 p. 2 promises shop-test data, but an actual engine shop-test report or measured fuel/load map was **not found in the inspected package**. REF02 engine ratings and REF04 propeller/model-tank tests are not equivalent to an engine shop-test consumption map. Fuel-saving estimates therefore require additional evidence even if a power difference is later established.

There is enough supplied reference material to document a **candidate comparison approach and its prerequisites**. There is not enough verified event/provenance evidence here to label a particular sensor period clean, attribute a power difference to fouling, or quantify a cleaning benefit. No comparison or new model was calculated in this audit.

## 5. What Task 2 does and does not document

**Already documented and worth retaining:** sensor-file counts/types, 2024 versus January 2025 channel coverage, sampling/alignment denominators, monthly target coverage, negative-power concerns, zero draft signals, weather repetition and timing uncertainty, limitations of the October association, and the daily Noon date coverage/timing concern (T2 §§1–5). These are real strengths; the gap is not a general absence of temporal or quality analysis.

| Required issue | Delivered-report finding | Smallest evidence-backed addition |
|---|---|---|
| Cleaning-event availability and provenance | **Missing.** No such source or availability statement in T2 §§1–6. | State “not found in the inspected package,” identify the search scope and distinguish promises/templates from actual logs. |
| Event temporal coverage | **Missing/unknown.** Sensor and Noon coverage is given, but there is no verified cleaning date, last prior cleaning, or before/after-event overlap. | Explicitly mark event coverage unknown; do not invent a clean start date or assume the first month is clean. |
| Event quality and completeness | **Not assessable from located data.** No event schema, timing precision, hull/propeller distinction, cleaning extent or inspection provenance. | Document which attributes could not be assessed because records were not located. |
| Reference-source inventory and domain background | **Missing from T2.** Vessel particulars, sea-trial chart, towing-tank clean-bottom assumptions and shop-test availability are not discussed. | Add a concise source/role/conditions/limitations table using §4 above. |
| Suitability for clean/current comparison | **Not explicitly assessed.** Existing EDA concerns regression reconstruction and pooled October relationships. | Explain that clean-reference identity, dated current window, comparable loading/weather/operating conditions and trustworthy power are prerequisites. Existing EDA is not a fouling estimate. |
| Loading support in Noon Reports | **Partial.** T2 §5 mentions displacement, but does not describe the populated forward/mid/aft drafts or their reference-comparison role. | Add these available fields, their daily cadence, unresolved units/timing and physical-consistency checks. Keep the zero-sensor-draft limitation. |
| Noon propulsion-consumption completeness | **Partial.** T2 §5 highlights June, but does not quantify missingness elsewhere. | Direct checks found 116 blank propulsion-consumption entries and 116 blank fuel-type entries across 366 dates, including all 30 June dates. If discussing fuel usefulness, report that broader limit. Blank does not mean zero consumption. |

A concrete loading-quality item for the suitability note is `data/Noon Reports/N03_March_Data_with_Propulsion_and_Fuel.csv`, CSV line 32 (31 March 2024): forward draft 5, mid draft 5.93, aft draft 1.29, displacement 34015. This warrants definition/transcription review before deriving trim or matching a reference; this audit does not declare it erroneous. The existing 18 slip flags are not cleaning indicators.

`Scientific_Validation.pdf` and its Markdown counterpart do not close these gaps. Their stated scope is sensor integrity, descriptive relationships and preliminary regression framing. Their check counts are not certification of business-objective alignment, event completeness or a validated clean-condition baseline. Historical statements about models not yet being trained were not checked against excluded Task 3 work.

## 6. Smallest necessary corrections

**Task 1:** Reframe the opening around the shipowner/performance team's maintenance decision; connect expected versus observed propulsion demand to possible excess-power review; position power estimation as an enabling objective. Identify intended users and decision actions. Retain uncertainty, single-vessel limitations and the absence of demonstrated savings. Add a short dependency on verified clean references/events. Move the existing method specification out of the business narrative rather than inventing new analysis.

**Task 2:** Add the missing source/availability table and short domain explanation of speed, loading, environment and clean/current condition. Record the bounded event-search result, unknown event coverage/quality, reference assumptions and the shop-test gap. Expand the existing Noon paragraph to cover draft/trim/displacement suitability and relevant missingness. Keep existing descriptive results and cautions; label their limits for condition comparisons. Relocate the proposed training/test allocation to later methods when revisions are authorized.

**Recommended business success measures, to agree with stakeholders rather than assign arbitrary targets:** proportion of operating periods for which a defensible comparison can be made; uncertainty relative to a maintenance-review threshold; frequency of alerts later explained by sensor/operating problems; and whether performance staff can make a supported inspect/clean/defer decision. Cleaning cost, downtime and validated benefit belong in later business evaluation. No accuracy target, saving percentage or cleaning recommendation is established by this audit.

## 7. Data and clarification required before a fouling-related claim

These are proposed requests; no message was sent to the professor, shipowner or organizer.

| Request | Why it matters / claim it constrains |
|---|---|
| Original event file or confirmed location, with event dates/times/timezones; last hull/propeller cleaning before the data period and all relevant events during it; separate hull cleaning, propeller polishing, dry docking, recoating and repairs | Establish temporal coverage, which component changed, and whether any clean-labelled or before/after window exists. Ask the provider to confirm completeness, not merely supply isolated dates. |
| Cleaning method/extent, inspection reports or condition assessments, and evidence supporting post-clean status | A cleaning date alone does not certify a fully clean condition or distinguish hull from propeller effects. Clarify simultaneous maintenance/configuration changes. |
| Authoritative clean-reference designation and full sea-trial/model-test provenance, original numeric curves, trial date/draft/trim/weather/depth, correction and uncertainty information, PSV applicability, and reference power definitions | Establish whether the engineering references apply to this dataset and how their power values relate to the torquemeter. Resolve the differing trial/report annotations without inferring identity. |
| Torquemeter calibration, zeroing, repair and operating logs; documented reliable periods, sign conventions and power-location definitions | Separate measurement problems from apparent performance changes. Existing negative-power anomalies do not establish exact fault boundaries. |
| Noon field units, observation/issue times and aggregation conventions; loading/ballast changes, voyage/operating-state metadata; speed-log and weather/current provenance | Compare equivalent conditions and explain changes that could mimic excess resistance. Validate draft/displacement/trim rather than copying daily values indiscriminately into minutes. |
| Definition of “current condition,” expected baseline and intended decision horizon; intended user, review threshold and action | Distinguish completed-minute monitoring from advance route planning and define an operational comparison that can actually support a decision. |
| If judging whether cleaning is worthwhile: actual shop-test or validated fuel-versus-load information, reliable fuel measurement, cleaning/port/off-hire costs, expected operating profile and benefit-duration assumptions | Needed for an economic case; an estimated power difference alone cannot establish a particular fuel saving or payback. |
| Professor/organizer clarification on whether the course selected a narrower power-estimation task, and the location of the promised event/shop-test data | Clarify the accepted scope while the Task 3 reply is pending. This audit finds a mismatch with the broader challenge, not evidence that every optional challenge task is mandatory for the course project. |

Pending that evidence, any future discrepancy should be described as **possible excess propulsion power relative to a stated reference**, with unresolved explanations. Fouling is one possible interpretation; loading, weather, operating state, configuration/reference mismatch and sensor problems must be considered. No excess-power amount, fouling attribution, hull/propeller separation, or particular fuel saving is established here.

## Section-by-section change plan — no revised deliverables created

### Task 1 — `Task 1 Report.pdf`

| Current section | Minimal proposed change | Destination / boundary |
|---|---|---|
| Title/status block | Replace the emphasis on preliminary technical findings with a business-problem status appropriate to the eventual revision; retain date/confidentiality and conditional language. | Do not infer current Task 3 status from the historical report. |
| **1. Problem and practical objective** (p. 1) | Lead with the performance/maintenance decision and clean-reference versus current demand; identify shipowner/performance and maintenance users. Keep power estimation/plausibility as enabling uses and distinguish monitoring from advance routing. | Move supervised-regression formulation, target QID and completed-minute mechanics to Task 2/later methods. Related Markdown: §1 and target part of §2. |
| **2. Candidate input measurements** (p. 1) | Replace the detailed channel-role table with a short business scope: decisions supported, intended outputs, and conditional/deferred objectives. State that hull-versus-propeller attribution is optional and unsupported without evidence. | Preserve channel inventory in Task 2; modelling exclusions belong in later methods. Related Markdown: §2. |
| **3. Data characteristics affecting the objective** (pp. 1–2) | Condense to business constraints: measurement reliability, one-vessel coverage, changing loading/weather, uncertain clean-state evidence. Add that cleaning records were not found in the inspected package. | Keep numeric anomaly/coverage details in Task 2. Related Markdown: §3. |
| **4. Proposed development and evaluation periods** (p. 2) | Remove the month-by-month split from the business section; use a brief staged decision scope: establish evidence, compare defensibly, then support maintenance review. | Preserve the existing split specification for later methods without assessing or revising Task 3. Related Markdown: §4. |
| **5. Success criteria and expected outputs** (p. 2) | Describe an interpretable, uncertainty-qualified performance comparison and stakeholder review criteria; distinguish potential value from measured savings. | Move MAE/RMSE/R² and technical baseline choices to later evaluation. Retain stakeholder agreement as a requirement. Related Markdown: §5. |
| **6. Working assumptions and next decisions** (p. 2) | Add the event-record and clean-reference requests, decision owner, definition of current condition, and scope clarification. Cite the original challenge and SINTEF business questions. | Retain reliability/availability conditions at business level; point to Task 2 for data detail. Related Markdown: §6. |

### Task 2 — `Task 2 Report.pdf`

| Current section | Minimal proposed change | Destination / boundary |
|---|---|---|
| **1. Dataset inventory / 1.1 Record structure and types** (p. 1) | Extend the inventory with event availability, Noon sources, particulars, sea-trial image, towing-tank clean-condition reference, templates and shop-test status. Add a brief domain paragraph connecting speed–power comparison to loading and environment. | Preserve sensor counts/types. Separate supplied data, reference predictions, templates and promised-but-unlocated sources. Related Markdown: §1. |
| **2. Sampling, temporal alignment and coverage / 2.1 Monthly observation-count density** (pp. 1–2) | Add an explicit temporal-coverage distinction: 2024 sensors/Noon dates, January 2025 without target, undated reference applicability, and unknown cleaning-event coverage. | Keep current sampling denominators and timing cautions; do not invent pre/post-clean windows. Related Markdown: §2. |
| **3. Sensor quality and candidate measurements / 3.1 Target-power anomalies** (pp. 2–4) | Connect existing sensor issues to comparison suitability; add reference power/configuration/condition checks and state that event quality cannot be assessed without the records. | Preserve documented sensor concerns; avoid treating channel eligibility or a reference curve as proof of a valid clean baseline. Related Markdown: §3. |
| **4. Relationships observed in October** (pp. 5–6) | Retain descriptive associations and their cautions. Add that these pooled relationships do not supply clean/current labels or fouling attribution, and identify the reference/matching evidence required for a later comparison. | No new plots, curve fitting, model evaluation or Task 3 investigation. Related Markdown: §4. |
| **5. Noon Reports and implications for modeling** (p. 7) | Describe all three draft fields and displacement as potential loading context, unit/timing issues and the physical-consistency review item; quantify fuel/consumption missingness if discussing fuel use. State no event field/entries were found. | Move the training/test allocation to later methods; keep data implications here. Related Markdown: §5. |
| **6. Interpretation and limitations** (p. 7) | Add a concise suitability conclusion: candidate engineering clean reference present; event-based clean labels, causal attribution and cleaning economics unverified. List the specific missing records and metadata. | Retain the existing no-accuracy/no-savings/deployment limits and source traceability. Related Markdown: §6. |

When revisions are later authorized, update the delivered PDFs and their confirmed editable sources consistently. Align the supporting validation document's scope with these additions without implying that its existing data checks validate cleaning claims. The present audit stops at this change plan; it creates no revised report and makes no Task 3 decision.
