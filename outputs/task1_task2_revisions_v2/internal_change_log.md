# Internal change log — controlled Task 1 / Task 2 revision

Date: 30 October 2026. Status: completed for internal review; nothing sent to the client.

## Authority, reconstruction and preservation

The authoritative historical deliveries are the project-root `Task 1 Report.pdf` (2 pages) and `Task 2 Report.pdf` (7 pages), dated 25 October 2026. Their content and section titles were used as the revision starting point. The existing `outputs/reports/task1_preliminary.md` and `task2_preliminary.md` were cross-checked as related drafts; they were not assumed to be the exact PDF sources.

A permitted-scope filename search found no report-authoring `.tex`, `.typ`, `.qmd`, `.rmd`, `.odt`, `.html` or report `.docx` source establishing the original PDF build chain. The only located DOCX in that search was the challenge Code of Conduct. The new authoritative editable sources are `task1_report_v2.md` and `task2_report_v2.md` in this revision directory. Both PDFs disclose this reconstruction in their edition-provenance notes. The retained historical proposal is explicitly labelled as such in Task 2 Appendix A. Historical extracted text is saved under `provenance/`; the original PDFs remain authoritative for their original rendering.

Only `outputs/task1_task2_revisions_v2/` was written. Original PDFs, raw data, existing reports/outputs and the scope audit were preserved. Task 3 results, models, metrics, predictions and V1–V8 investigation contents were neither inspected nor modified. The original challenge presentation bearing “V1” is a source document, not an investigation. No model, new performance result or clean/current comparison was produced. `Scientific_Validation.pdf` is an unchanged supporting source, not a revised deliverable.

Source justification shorthand below follows the PDF reference lists: C1 announcement; C2 original challenge presentation; C3 SINTEF presentation; C4 course rubric; R1/R2 delivered Task 1/2; A1 scope audit findings; A2 scope audit inventory; D1 registration; D2 existing inventory metadata; V1 particulars; V2 sea-trial chart; V3 towing-tank report; N1 Noon Reports; X1 CSV templates; M1 related Markdown drafts; S1 scientific-validation PDF. Exact paths and page/section locators appear in the revised reports and the immutable scope audit.

## Task 1: substantive changes and source justification

| ID | Delivered location / current title | Revision and destination | Source justification |
|---|---|---|---|
| T1-01 | Title/status: preliminary technical findings | New v2 date and business-scope status; original date/content remain preserved. New edition provenance records reconstruction. | User's controlled-revision instructions; R1; A1 review-authority section. |
| T1-02 | §1 Problem and practical objective | Primary problem now compares observed propulsion demand against a defensible clean-condition reference: more power at a given speed or less speed at a given power, under comparable conditions. | C1 PDF p. 3 tasks 1–2; C2 slides 3 and 7; C3 PDF p. 13; A1 §§1–2. |
| T1-03 | §1 | Connects evidence to investigation, inspection, consideration of cleaning or deferral by performance/maintenance users; adds operational-efficiency relevance without a savings estimate. | C1 PDF p. 1; C3 PDF pp. 3 and 13; A1 §§1, 6. |
| T1-04 | §1 | Retains power estimation/plausibility as an enabling capability; distinguishes reconstruction of current power from an independently justified clean reference. | R1 §1; C1 PDF p. 3 task 3; C3 PDF p. 13; A1 §2. |
| T1-05 | §1 and §2 Candidate input measurements | Moves QID, completed-minute specification, channel accounting and modelling exclusions to Task 2 data sections / Appendix A. | C4 PDF pp. 7–9; R1 §§1–2; A1 section change plan. No technical result is discarded or recomputed. |
| T1-06 | §2 Candidate input measurements | Renamed **Business users and supported decisions**. Adds proposed user roles and outputs, explicitly subject to stakeholder agreement rather than implying named appointments. | C4 PDF pp. 8–9; C3 PDF p. 13; A1 §§2, 6. Role allocation is a proposal, not a newly verified organizational fact. |
| T1-07 | §3 Data characteristics affecting the objective | Condenses detailed counts into decision-relevant reliability, coverage, loading/weather and single-vessel constraints; numerical evidence remains in Task 2. | R1 §3 and R2 §§1–4; A1 §§2, 5. |
| T1-08 | §3 | Adds bounded cleaning-record/shop-test availability findings and distinguishes engineering clean-bottom assumptions from a dated clean observed interval. | A1 §§3–4 and A2; V3 PDF p. 12. No event date or clean label added. |
| T1-09 | §4 Proposed development and evaluation periods | Renamed **Scope and staged decision process**. Describes evidence, comparability, feasibility and maintenance review. Original month allocation moves intact in substance to Task 2 Appendix A.2. | R1 §4; C4 report structure; A1 change plan. Pending Task 3 decisions are not assessed. |
| T1-10 | §4 | Explicitly bounds advance routing, optional hull/propeller separation and economic assessment. | C1 PDF p. 3 task 5; C3 PDF p. 13; R1 §§1, 5; A1 §§1, 7. |
| T1-11 | §5 Success criteria and expected outputs | Replaces the main technical-metric argument with proposed reference/condition coverage, decision uncertainty, reliability of review indications and usefulness to the reviewer. No targets or benefits invented. | C4 PDF pp. 8–9; A1 §6. Measures are recommendations for stakeholder agreement. |
| T1-12 | §5 | Moves MAE/RMSE/R², baseline choices and chronological technical-success specification to historical Appendix A.3 in Task 2. | R1 §5, reproduced as a proposal; A1 change plan. No metric values or new accuracy claim. |
| T1-13 | §6 Working assumptions and next decisions | Adds event/inspection history, reference provenance, trustworthy observations, current-window/decision-horizon definitions and scope clarification. Retains calibration/timing/availability dependencies. | R1 §6; A1 §7; A2 missing-evidence records. |
| T1-14 | References / edition provenance | Adds explicit source citations and reconstruction provenance, with links from PDF citations to reference entries. | Original sources in A2; user's traceability and source-preservation requirements. |

## Task 2: substantive changes and source justification

The six delivered main section titles and original subsections 1.1, 2.1 and 3.1 are retained. Added subsections and appendices support the expanded source understanding without changing the reported descriptive results.

| ID | Delivered location / current title | Revision and destination | Source justification |
|---|---|---|---|
| T2-01 | §1 Dataset inventory; §1.1 Record structure and types | Retains record/QID counts, target absence in January 2025, finite parsing, duplicate/short-row findings, types and timezone/aggregation caveats. Labels them as retained earlier findings rather than a new full-data audit. | R2 p. 1; D1/D2; supporting M1. |
| T2-02 | §1 | Adds brief domain context connecting speed, loading/trim, environment and operating state to reference comparability. | C1 PDF p. 3 task 1; C3 PDF pp. 5–7; A1 §4. |
| T2-03 | New §1.2 Compact source inventory | Adds eight source rows: sensor series, Noon Reports, particulars, sea trials, towing-tank report, cleaning events, actual shop-test data, and CSV templates. Differentiates observations, reference predictions, examples and unavailable evidence. | A1 §§3–4; A2 individual source records; references D2, N1, V1–V3, X1. |
| T2-04 | New §1.2 / §1.3 | Explicitly states cleaning-event records were not found in the inspected package; event coverage/completeness/extent and quality cannot be assessed. | A1 §3 search evidence; A2 SEARCH/GAP and file/member entries. Announcement alone is not treated as proof of availability. |
| T2-05 | New §1.2 / §6 | Records that an actual engine shop-test report/fuel-load map was not found, and distinguishes engine ratings / propeller model tests from that evidence. | A1 §4 shop-test distinction; A2 GAP02; V1/V3. |
| T2-06 | New §1.2 / §1.3 | Identifies template clean/fouling flags as examples, not ground-truth events; avoids converting any template timestamp into a cleaning date. | A1 §3 false positives; A2 TPL01/TPL02; X1. |
| T2-07 | New §1.3 Engineering reference versus observed clean condition | Makes explicit that the clean-bottom engineering prediction does not prove a dated clean sensor period. No first month or post-gap period is labelled clean. | V3 PDF p. 12; V2 limitations; A1 §§3–4. |
| T2-08 | §2 Sampling, temporal alignment and coverage / §2.1 Monthly observation-count density | Preserves all three missingness denominators, trailing-minute convention, 60-minute past-timestamp rule, source overlap, repeated-weather caution, all twelve monthly rows and 16-of-31 October date coverage. | R2 pp. 1–2; M1 for exact interval boundaries; all monthly rows checked against the delivered PDF. |
| T2-09 | §2 | Adds distinction between known sensor/Noon coverage, unknown event chronology and January 2025's absent target; requires an explicit usable “current” window. | R2 pp. 1–2, 7; A1 §§3–5. |
| T2-10 | §3 Sensor quality and candidate measurements | Preserves 36-channel role accounting, 24 candidates, 8,226,522 zero draft values, source/unit and circular-variable caveats; adds that reconstruction roles do not validate a clean-reference model. | R1 §2; R2 pp. 2–4; D1/D2; A1 §2. |
| T2-11 | §3.1 Target-power anomalies | Preserves July/November counts, dates, runs and joint operating conditions. Renders −24,757 kW explicitly; no new numeric result. Retains unknown cause, no silent clipping, June caution and December caveat. | R2 p. 4; M1 and S1 confirm the negative sign and above-3-kn condition; C3 PDF p. 13. |
| T2-12 | §3 / §6 | Explains why sensor reliability and comparable operating conditions are prerequisites to interpreting a power difference. | R2 target/representativeness cautions; C3 PDF pp. 5–7, 13; A1 §§4–7. |
| T2-13 | §4 Relationships observed in October | Retains the seven correlations/pair counts, binned medians, descriptive cubic values, speed-cubed caveat and unresolved causes. Explicitly states that these are retained EDA, with no refit or fouling interpretation. | R2 pp. 5–6; M1. Seven correlation/count pairs mechanically checked against the delivered PDF. |
| T2-14 | §5 Noon Reports and implications for modeling | Retains 366 dates, daily cadence, slip flags and timing limits. Adds all three populated draft fields, displacement, unconfirmed units and the distinction from particulars' displacement volume. | R2 p. 7; A1 §§4–5; N1; V1. |
| T2-15 | §5 | Adds already-audited 116 blank consumption and 116 blank fuel entries, all 30 June dates missing, the 31 March loading review item, and absence of cleaning fields/entries. No new calculation made for the revision. | A1 §5; A2 NOON entries; N1 exact March file/line. The loading item is a review flag, not a declared error. |
| T2-16 | §5 / Appendix A | Relocates the original evaluation split to a historical technical appendix, preserving chronology, quarantine roles and December policy caveat. | R1 §4; R2 §5. No later results/metrics/models inspected. |
| T2-17 | §6 Interpretation and limitations | Adds reference-configuration, power-location, speed/loading/environment, correction/uncertainty requirements; includes sea-trial/towing annotation reconciliation and the prohibition on interpreting PSV differences as cleaning savings. | V2 chart; V3 PDF pp. 8, 10–14; A1 §4. Difference is not asserted to prove a vessel mismatch. |
| T2-18 | Appendix B | Reproduces all six figures extracted directly from the delivered PDF, retaining figure numbers and substantive captions. Figure 2 gains a clarification that roles belong to the original reconstruction proposal. | R2 original pp. 2–6; original image hashes and final PDF pixel hashes match for all six images. No chart regenerated. |
| T2-19 | References / edition provenance | Adds exact source references, internal citation links, reconstruction disclosure and retained-figure provenance. | A2 source inventory; user's controlled-revision instructions. |

## Checks completed

Automated document validation: **23 PASS, 0 FAIL**. Details are in `qa/validation_results.json`; this is document QA, not scientific validation of a new performance result.

| Check area | Result and scope |
|---|---|
| Original/source preservation | 52 explicitly protected files retain size and modification time; 39 small source files also retain SHA-256 content hashes. This includes original PDFs, both immutable audit artifacts, supporting sources and raw-file metadata. Large raw CSV contents were not reread for hashing. |
| Authoritative-source/PDF consistency | All 55 Task 1 and 256 Task 2 text blocks/table cells are represented in extracted PDF text after typography normalization. |
| Text extraction | PyMuPDF and pypdf extract both revised PDFs successfully; no replacement/NUL/square glyphs detected. The signed −24,757 and −60% values extract correctly. |
| Pagination and rendering | Task 1 has 3 pages; Task 2 has 11. All 14 pages rasterize at 108 dpi. No blank pages; final layouts avoid the initial two-line spillover and figure separation. |
| Tables / page bounds | All paragraph, table and image rectangles lie within the content frame. Text spans remain within page margins. A detected initial table-width overrun was corrected by using the frame's actual padded width. |
| Retained numeric content | All twelve monthly count/density/negative rows and seven correlation/pair-count combinations match the original Task 2 PDF. Key existing inventory, alignment, quality and EDA values remain present. |
| Figures | Six images in the revised Task 2 PDF match the six original figure pixel hashes. Figure numbering/captions retained; only display size/placement changed. |
| References | All 17 Task 1 and 95 Task 2 internal citation links resolve to pages in the respective PDF. Source/reference IDs and paths reviewed against the inspected documents and audit. |
| Cross-report consistency | Both reports use the same bounded evidence-availability conclusions, condition-comparison rationale and absence of new claims. Task 1 correctly points to Task 2 Appendix A for historical technical material. |
| Visual inspection | All pages reviewed through rendered contact sheets; dense source/coverage tables, business pages, Noon/limitations, references and figures additionally inspected at page size. No clipping, overlapping cells, cropped figures or orphaned captions observed in the final rendering. |

`qa/final_render/` contains the final page images/contact sheets. `qa/initial_render/` contains superseded first-build layout checks only and is not a deliverable. The authoritative PDFs and current editable sources are at the revision-directory root.

## Remaining limitations

- Cleaning-event records and an actual engine shop-test report/map remain **not found in the inspected package**. No claim is made about other locations. Event dates, completeness, cleaning extent and dated clean-state evidence remain unknown.
- The sea-trial and towing-tank references still need provenance/configuration, power-definition, correction and applicability confirmation. An engineering clean-bottom assumption does not certify an observed clean interval.
- Torquemeter reliable periods, external timestamp meaning, engine-signal availability and Noon units/timing/loading representativeness remain unresolved. These are stated limitations, not fixed by rewording the reports.
- The retained descriptive findings were not recomputed. No performance comparison, fouling attribution, new accuracy result, fuel-saving or cost-benefit estimate is established.
- Stakeholder roles and success-measure principles are proposals; named responsibilities, thresholds and accepted course scope still need agreement. The professor's Task 3 reply remains pending; that work was excluded.
- The exact original PDF build source remains unavailable in the inspected scope. These newly reconstructed Markdown files are authoritative only for the v2 editions.

No client communication, publication or deployment occurred.
