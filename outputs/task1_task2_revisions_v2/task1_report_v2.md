# Task 1 — Problem Definition and Business Understanding

SINTEF Ocean Real Vessel Data Challenge | TDT4259 Applied Data Science

**Version 2 · 30 October 2026 · Business scope and decision requirements**

## 1. Problem and practical objective

The business problem is to determine whether the vessel requires more propulsion power at a given speed, or achieves less speed at a given power, than a defensible clean-condition speed–power reference would indicate under comparable operating conditions. A credible comparison could help the shipowner's performance and maintenance teams decide whether to investigate a performance change, arrange an inspection, consider hull or propeller cleaning, or defer action while obtaining better evidence.

This framing follows the challenge's clean- and current-condition baseline objectives and its request to estimate added power or speed loss. The SINTEF presentation explicitly asks whether performance indicates a need for hull and/or propeller cleaning and, additionally, whether cleaning is worthwhile. Fuel costs and operational efficiency motivate the work, but the value of a specific maintenance action must be assessed separately. [C1, C2, C3]

**The intended comparison is conditional:** speed, loading, trim, environmental conditions and operating state must be comparable, and both the reference and observed power must be trustworthy. A difference is initially a possible excess-power or speed-loss indication. It does not establish fouling or identify its location. Sensor problems, reference mismatch and changing operating conditions remain alternative explanations.

Shaft-power estimation remains an enabling capability. It may provide a secondary indication of propulsion demand, support a plausibility check or help address missing observations where justified. An estimate that reproduces current power is not automatically an estimate of clean-condition power. The reference condition requires its own evidence. Technical details preserved from the original delivery are recorded in Task 2 v2, Appendix A. [R1, R2, A1]

## 2. Business users and supported decisions

The following are intended user roles; specific people, responsibilities and acceptance thresholds must be agreed with the project stakeholders.

| Intended user | Supported decision and intended output |
|---|---|
| Shipowner / vessel performance team | Review a dated, uncertainty-qualified comparison of observed demand with an applicable reference; decide whether the indication warrants investigation. |
| Technical superintendent / maintenance planner | Combine performance evidence with inspection and maintenance history to consider inspection, cleaning or deferral. |
| Vessel engineers / operational staff | Check measurement reliability, loading changes and operating circumstances that could explain a performance indication. |
| Operations / commercial decision owner | Assess scheduling and economic implications once cleaning scope, cost, downtime and credible benefit evidence are available. |

The supported output is a documented basis for maintenance review. Cleaning remains a human decision informed by operational evidence; this report does not recommend a particular cleaning event.

<!-- pagebreak -->

## 3. Data characteristics affecting the objective

The package contains operational sensor data, daily Noon Reports and engineering references, but the evidence has important limits. The delivered data analysis identifies suspect shaft-power readings, uneven coverage, unusable sensor draft values, repeated weather observations and uncertain timestamp semantics. These issues can make an apparent performance change unreliable. A single vessel and changing loading, weather and operating states also constrain generalization. Task 2 retains the numerical findings and their qualifications. [R2]

Actual hull/propeller **cleaning-event records were not found in the inspected package**. The available towing-tank report explicitly predicts performance with a clean bottom under specified conditions, but this does not prove that any dated interval in the observed sensor series represents a clean vessel. The sea-trial image also needs fuller provenance before use as a validated reference. An actual engine shop-test report or fuel/load map was not found in the inspected package. [A1, A2]

## 4. Scope and staged decision process

The project should first establish reference applicability, trustworthy observation periods and comparable operating conditions. It can then assess whether an interpretable performance comparison is feasible and, if supported, present possible excess power or speed loss with uncertainty for maintenance review. This revision defines that decision process; it does not calculate the comparison.

The original completed-minute shaft-power reconstruction remains a supporting use. Advance route planning requires a separately defined decision horizon and inputs available at that time. Distinguishing hull from propeller fouling is optional in the original challenge and requires additional evidence. Estimating fuel savings or deciding whether cleaning is economically worthwhile is conditional on validated performance and cost information. [C1, C3, R1]

## 5. Success criteria and expected outputs

Success should be judged by whether the evidence supports a useful and appropriately qualified decision. The following principles are proposed for agreement with stakeholders; no numerical acceptance threshold or achieved benefit is asserted.

| Success-measure principle | What the eventual output should make assessable |
|---|---|
| Reference and condition coverage | The share of relevant operating periods with trustworthy observations and an applicable reference at comparable conditions; unsupported periods remain explicit. |
| Decision-relevant uncertainty | Whether uncertainty is small enough relative to an agreed maintenance-review threshold to justify investigation or action. |
| Reliability of review indications | How often a flagged change is subsequently explained by measurement or operating conditions, and how that affects confidence in future reviews. |
| Usefulness to the decision owner | Whether performance staff can document a supported inspect, consider-cleaning or defer decision, with evidence and unresolved questions visible. |

Intended outputs are a reference-applicability statement, a clearly dated comparison window, a qualified power/speed indication where defensible, and a concise maintenance-review brief. Technical prediction accuracy is an enabling quality measure, not a substitute for these decision requirements. No fouling detection, accuracy result, cleaning saving, fuel saving or cost-benefit estimate is demonstrated in this revision.

<!-- pagebreak -->

## 6. Working assumptions and next decisions

The next evidence requests are the cleaning and inspection history, including the last relevant event before the observation period; confirmation of the clean-reference conditions and vessel configuration; torquemeter calibration and operating records; and loading, weather and time-semantics metadata. These requests should establish event completeness, clean-state provenance and comparable conditions without assigning unverified clean labels. Task 2 explains the source-specific limitations. [A1, A2]

Stakeholders should agree the definition of “current condition,” the decision horizon, the responsible reviewer and an acceptable uncertainty/alert policy. Economic evaluation additionally requires credible fuel-conversion information, cleaning and downtime costs, and an intended operating profile. No particular cost or saving is assumed.

The course's accepted scope should be confirmed with the professor/organizer while the Task 3 reply is pending. The historical technical proposal is preserved for traceability in Task 2 v2, Appendix A; it has not been reassessed against later work. This revision addresses Task 1 and Task 2 only. Data attribution and vessel confidentiality remain part of the reporting requirements. [C3, C4]

## References and edition provenance

References use project-relative paths. The corresponding Task 2 v2 report provides the detailed source inventory and technical appendix.

[C1] `docs/challenge/HullPIC25 Announcement.pdf`, PDF pp. 1–3 (printed pp. 117–119): shipowner context, clean/current baselines, added power/speed loss, missing-data estimates, quality/uncertainty and optional hull/propeller distinction.

[C2] `docs/challenge/Big Data from ships Challenge V1.pptx`, slides 3–9: original challenge objectives, source types and output formats.

[C3] `docs/SINTEF_Ocean_v2.pdf`, PDF pp. 3, 5–7 and 13 (p. 13 is printed slide 14): business motivation, performance influences, cleaning and prediction questions; p. 12: source-use conditions.

[C4] `docs/2026_Lecture2_Dataset.pdf`, PDF pp. 7–9: business understanding, data understanding and later technical evaluation criteria.

[R1] `Task 1 Report.pdf`, delivered 25 October 2026, pp. 1–2: original objective and technical proposal.

[R2] `Task 2 Report.pdf`, delivered 25 October 2026, pp. 1–7: retained descriptive evidence and limitations.

[A1] `outputs/task1_task2_scope_audit/internal_findings.md`, 30 October 2026, §§1–7: scope review, bounded source search, suitability findings and requests.

[A2] `outputs/task1_task2_scope_audit/source_inventory.csv`: exact source paths, inspection scope and provenance evidence supporting [A1].

**Edition provenance:** The v2 editable source was reconstructed from the delivered PDFs and cross-checked against the related Markdown drafts. An exact editable source/build chain for the original PDFs was not found in the inspected scope. Existing documents remain preserved; this edition adds no performance analysis.
