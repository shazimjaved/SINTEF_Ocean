# Task 1 / Task 2 — controlled v2 revision

The revised PDFs and their new authoritative editable sources are:

| Report | PDF | Editable source |
|---|---|---|
| Task 1 — business scope and decision requirements | [Task 1 Report v2.pdf](Task%201%20Report%20v2.pdf) — 3 pages | [task1_report_v2.md](task1_report_v2.md) |
| Task 2 — data understanding and source suitability | [Task 2 Report v2.pdf](Task%202%20Report%20v2.pdf) — 11 pages | [task2_report_v2.md](task2_report_v2.md) |

The original project-root PDFs are the historical delivery authority. An exact editable source/build chain for them was not found in the inspected scope. These v2 sources were reconstructed from their content and section titles and cross-checked against the related Markdown drafts. Task 1 intentionally renames two technical section headings to fit the business narrative; the old technical specification is retained in Task 2 Appendix A. All six original Task 2 figures are retained in Appendix B.

[internal_change_log.md](internal_change_log.md) records every substantive change, its source justification, completed checks and unresolved evidence. No files outside this revision directory were changed, and nothing was sent to the client. The existing scientific-validation report was not revised.

## Build and validation

`build_reports.py` uses ReportLab to render the authoritative Markdown sources and the extracted original images in `assets/`. It performs no data analysis and does not read Task 3 artifacts. It uses the existing local Python packages and Calibri/Consolas fonts from `C:/Windows/Fonts`.

From the project root, a fresh build is:

```powershell
python -B outputs/task1_task2_revisions_v2/build_reports.py
```

It refuses to overwrite an existing generated PDF unless `--replace-generated` is supplied. That option is limited to the two v2 PDFs in this directory; it never writes the historical PDFs. The supported Markdown includes headings, bold/code, pipe tables, citation references, images and explicit `<!-- pagebreak -->` directives.

Document validation is:

```powershell
python -B outputs/task1_task2_revisions_v2/validate_reports.py
```

The completed check result is **23 PASS, 0 FAIL**, plus visual review of the rendered pages. Validation checks document completeness, retained numerical content/figures, references, rendering and source preservation. It is not a new scientific or model evaluation.

## Supporting records

- `provenance/protected_sources.json`: pre-revision size/time records for 52 protected files and content hashes for 39 small files.
- `provenance/task1_delivered_text.txt` and `task2_delivered_text.txt`: extracted historical PDF text; original PDFs remain authoritative where extraction loses a glyph.
- `provenance/figure_manifest.json`: original PDF page/xref, image size and byte/pixel fingerprints for six extracted figures.
- `provenance/build_manifest.json`: current source/PDF fingerprints and reference/table/figure counts.
- `qa/validation_results.json`: detailed document checks.
- `qa/task1_v2_extracted_text.txt` and `task2_v2_extracted_text.txt`: final extracted text.
- `qa/final_render/`: final rendered pages and contact sheets.
- `qa/initial_render/`: superseded initial layout diagnostics, retained only for internal build traceability.

Cleaning-event records and an actual shop-test report/map remain not found in the inspected package. Reference provenance/applicability, calibration and loading/timing metadata still require clarification. The revision makes no new performance comparison or fouling, accuracy, savings or cost-benefit claim.
