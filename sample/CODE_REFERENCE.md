# Code Reference Index — File & Line Number Guide

**For reviewers:** Every item below uses the format **`filename` → lines `START–END`**. Open the file in any editor and jump directly to that line (VS Code/Cursor: `Ctrl+G` / `Cmd+G`).

All paths are relative to the `sample/` folder unless noted.

---

## Quick Start: Follow the Pipeline in Order

| Step | What happens | File | Lines to read |
|------|--------------|------|---------------|
| 1 | PDF → JSON + `_pl.txt` | `archive/pdf_extractor.py` | **596–724** (CLI entry), **669–696** (writes output files) |
| 2 | Extract 4 P&L metrics | `extract_pl_metrics_v2.py` | **1066–1079** (run), **883–1025** (single-file logic), **1027–1064** (batch) |
| 3 | Audit extraction accuracy | `audit_pl_metrics.py` | **17–78** |
| 4 | Review completeness | `create_pl_review.py` | **39–172** |
| 5 | Merge manual fixes | `consolidate_final.py` | **150–165** |
| 6 | Profit shifting flags | `analyze_profit_shifting.py` | **100–192** |
| 7 | Quick lookup | `find_pl_numbers.py` | **83–131** |

---

## Master Function Index (All Active Scripts)

### `extract_pl_metrics_v2.py` — Main P&L Extractor

| Function / Constant | Lines | Purpose |
|---------------------|-------|---------|
| Module docstring | **1–5** | What this file does |
| `extract_number()` | **12–44** | Parse accounting numbers; filter year noise; pick largest value |
| `extract_lines_from_json()` | **47–97** | Read text lines from companion `.json` |
| `extract_statement_source_text()` | **100–126** | Best full text for statement parsing |
| `parse_accounting_token()` | **147–157** | Parse `(1,234)` → negative float |
| `parse_amount_token()` | **160–192** | OCR-corrupted amounts (e.g. `796,1Sl`) |
| `normalize_pl_label()` | **195–214** | OCR fuzzy label fix (`turniwer` → turnover) |
| `fuzzy_has_turnover()` | **217–223** | Detect turnover despite OCR errors |
| `STATEMENT_HEADING_RE` | **234–238** | Regex for P&L section headings |
| `find_interleaved_year_header()` | **247–253** | Two-year column headers (2018/2017) |
| `infer_year_from_stem()` | **256–258** | Year from filename |
| **`find_best_statement_block()`** | **261–358** | **Layer 1 guardrail:** locate income statement in full text |
| `extract_inline_pl_metrics()` | **361–385** | Row-style tables (`Turnover 2 34,711`) |
| `parse_columnar_rows()` | **400–421** | Row labels from columnar layout |
| `columnar_row_index()` | **424–437** | Map label → row index |
| `resolve_target_year()` | **440–467** | Pick current vs comparative year column |
| `extract_interleaved_columnar_pl_metrics()` | **471–548** | Interleaved year/value columns |
| `extract_ocr_gartner_pair_metrics()` | **551–586** | Heavily corrupted Gartner OCR tables |
| `extract_columnar_pl_metrics()` | **589–640** | Stacked year columns (`2018\n€'000\n...`) |
| **`extract_metrics_from_statement_block()`** | **643–724** | **Primary extraction:** table block → 4 metrics |
| `find_income_statement_start()` | **727–768** | Keyword-neighborhood search anchor |
| `is_narrative_line()` | **771–786** | Skip prose lines (not table rows) |
| `extract_value_after_keyword()` | **813–830** | Value on same line after label |
| **`find_metric_value()`** | **832–881** | **Fallback:** keyword search + lookahead |
| **`extract_pl_metrics()`** | **883–1025** | **Orchestrator:** JSON + TXT → metrics dict |
| Turnover keyword search | **949–953** | Keywords + `min_abs=500` |
| Operating profit search | **956–960** | Keywords + `min_abs=50` |
| Profit before tax search | **963–969** | Keywords + confidence bump |
| Profit/loss for year search | **972–979** | Bottom-line keywords |
| Fallback pass (full doc) | **981–1013** | Only if statement block incomplete |
| Confidence scoring | **1015–1023** | `high` / `medium` / `low` |
| `process_all_pl_files()` | **1027–1064** | Batch: all `*_pl.txt` → `pl_metrics_cleaned/` |
| `if __name__ == '__main__'` | **1066–1079** | Script entry point |

---

### `analyze_profit_shifting.py` — Red-Flag Analysis

| Function / Section | Lines | Purpose |
|--------------------|-------|---------|
| Config paths | **8–10** | Input folder `pl_metrics_cleaned/` |
| `analyze_profit_shifting()` | **12–98** | Group by company ID; compute margins |
| Company ID parsing | **28–31** | Split filename on `_` |
| Net profit margin calc | **64–72** | Flag if margin < 1% or negative |
| Operating margin calc | **74–76** | Operating profit / turnover |
| Large profit reduction flag | **78–85** | Operating − net > 10% of turnover |
| Unusual op vs net flag | **87–90** | Operating < 50% of net profit |
| `generate_report()` | **100–192** | Load JSON, write CSV, print summary |
| CSV output columns | **123–135** | Header row definition |
| CSV row write | **137–156** | One row per analyzed record |
| `if __name__ == '__main__'` | **194–195** | Script entry point |

---

### `audit_pl_metrics.py` — Extraction Validator

| Function / Section | Lines | Purpose |
|--------------------|-------|---------|
| Imports from v2 | **8–14** | Reuses extraction functions |
| `main()` | **17–78** | Compare extracted vs statement-block reference |
| Mismatch loop | **22–64** | Per file, per metric comparison |
| Output write | **74–78** | `pl_metrics_cleaned/audit_mismatches.json` |
| `if __name__ == "__main__"` | **81–82** | Script entry point |

---

### `create_pl_review.py` — Completeness Report

| Function | Lines | Purpose |
|----------|-------|---------|
| `get_metrics_from_file()` | **13–20** | Load `all_pl_metrics.json` |
| `calculate_completeness()` | **23–26** | % of 4 metrics filled |
| `get_notes_for_metric()` | **29–36** | INCOMPLETE / currency notes |
| `create_review_report()` | **39–172** | Write `pl_metrics_review.csv` + stats |
| Summary statistics | **84–118** | Fully / partially / empty counts |
| `if __name__ == "__main__"` | **175–176** | Script entry point |

---

### `consolidate_final.py` — Merge Corrections

| Function | Lines | Purpose |
|----------|-------|---------|
| Config | **5–7** | Output folder |
| `load_existing_metrics()` | **10–28** | Load individual `*_metrics.json` |
| `load_table_metrics()` | **31–38** | Load `all_pl_metrics.json` |
| `merge_metrics()` | **41–79** | Prefer existing; fill gaps from batch |
| `save_final_metrics()` | **82–85** | Write `all_pl_metrics_final.json` |
| `print_summary()` | **88–147** | Console table |
| `main()` | **150–165** | Orchestrator |
| `if __name__ == "__main__"` | **164–165** | Script entry point |

---

### `find_pl_numbers.py` — CLI Lookup

| Function | Lines | Purpose |
|----------|-------|---------|
| Config | **9–12** | CSV path |
| `load_companies()` | **15–39** | Read summary CSV |
| `display_results()` | **42–80** | Print all companies |
| `find_pl_numbers()` | **83–102** | Main display + file paths |
| `search_company()` | **104–123** | Filter by search term |
| `if __name__ == '__main__'` | **125–131** | CLI: no args = all; arg = search |

---

## Archive: PDF Extraction (`archive/pdf_extractor.py`)

| Function / Section | Lines | Purpose |
|--------------------|-------|---------|
| Module docstring | **1–5** | PyMuPDF-based full PDF extraction |
| `extract_metadata()` | **20–28** | Title, page count, etc. |
| `extract_page_attributes()` | **31–42** | Width, height, rotation per page |
| **`extract_text()`** | **45–58** | **`text.by_page` + `text.full_text`** — used by v2 extractor |
| `extract_images()` | **61–85** | Image metadata |
| `_parse_pl_table_block()` | **178–217** | Parse label + value rows |
| **`extract_profit_and_loss_table()`** | **220–271** | Find P&L heading → parse table |
| `get_pdf_paths()` | **274–288** | Collect PDFs from directory |
| **`extract_all_attributes()`** | **291–324** | **Main PDF → dict converter** |
| **`extract_current_directors()`** | **327–507** | Directors from metadata, forms, text |
| Role pattern `Name - Director` | **399–414** | Regex at line 401 |
| Directors block pattern | **416+** | Section between headings |
| `extract_year_ended()` | **509–541** | "Year ended 31 December 2020" |
| `extract_company_name()` | **543–580** | From metadata title or first line |
| **`main()`** | **596–724** | CLI: process all PDFs |
| Write JSON per PDF | **676–677** | `{stem}.json` |
| Write `_pl.txt` if table found | **679–696** | `{stem}_pl.txt` |
| `if __name__ == "__main__"` | **725+** | Script entry point |

---

## Archive: Directors Extraction

| File | Function | Lines | Purpose |
|------|----------|-------|---------|
| `archive/extract_directors.py` | `extract_directors_from_pdf()` | **27–52** | PDF → company, year, directors |
| `archive/extract_directors.py` | `main()` | **54–116** | Batch; writes `directors_output/` |
| `archive/extract_directors_v4.py` | `extract_directors_clean()` | **17–86** | Text-based director parsing |
| `archive/extract_directors_v4.py` | `main()` | **88–119** | Batch from `_pl.txt` files |
| `archive/extract_directors_clean.py` | `extract_directors_from_text()` | **34–114** | Structured role extraction |
| `archive/scripts/extract_directors_final.py` | `extract_directors_structured()` | **23–116** | Final structured version |

---

## Archive: Principal Activity Extraction

| File | Function | Lines | Purpose |
|------|----------|-------|---------|
| `archive/extract_principal_activity.py` | `extract_section()` | **9–68** | Principal Activity / Business Review |
| `archive/extract_principal_activity.py` | `main()` | **70–132** | Batch → `principal_activity_outputs/` |
| `archive/principal_activity_v2.py` | `extract_principal_activity_v2()` | **9–53** | Improved section detection |
| `archive/principal_activity_BGversion.py` | `extract_principal_activity()` | **19–68** | BG version with normalization |
| `archive/scripts/principal_activity.py` | `extract_principal_activity()` | **16–99** | Script folder version |
| `archive/ocr_cleaner.py` | `OCR_CORRECTIONS` dict | **10–90** | Known OCR typo replacements |
| `archive/ocr_cleaner.py` | `correct_ocr_errors()` | **92–104** | Apply corrections |
| `archive/ocr_cleaner.py` | `main()` | **106–157** | Clean principal activity files |

---

## Archive: Validation & Reports

| File | Function | Lines | Purpose |
|------|----------|-------|---------|
| `archive/check_financial_tables.py` | `REQUIRED_FIELDS` | **11–18** | Six required P&L row labels |
| `archive/check_financial_tables.py` | `check_text_file()` | **20–39** | Verify fields in `_pl.txt` |
| `archive/check_financial_tables.py` | `main()` | **75–167** | Full verification report |
| `archive/comprehensive_report.py` | `extract_principal_activity()` | **19–63** | Activity section |
| `archive/comprehensive_report.py` | `check_financial_fields()` | **65–79** | Field presence check |
| `archive/comprehensive_report.py` | `main()` | **81–166** | Combined report |

---

## Archive: Earlier Extraction Versions (`archive/scripts/`)

| File | Key function | Lines | Notes |
|------|--------------|-------|-------|
| `extract_pl_metrics.py` | `extract_pl_metrics()` | **244–318** | v1 extractor (superseded) |
| `extract_pl_metrics.py` | `process_all_pl_files()` | **320–398** | v1 batch |
| `extract_cleaned.py` | `find_pl_table_section()` | **68–293** | 4-layer guardrail prototype |
| `extract_cleaned.py` | `fuzzy_match()` | **32–48** | OCR fuzzy matching |
| `extract_table_metrics.py` | `find_pl_table()` | **14+** | Table-structure parser |
| `fresh_ocr_extraction.py` | `find_pl_section()` | **98–123** | pdfplumber P&L section |
| `fresh_ocr_extraction.py` | `extract_metrics_from_text()` | **126–154** | OCR metric extraction |
| `fresh_ocr_extraction.py` | `main()` | **255–291** | Batch OCR pipeline |
| `enhanced_ocr_extraction.py` | `parse_pl_table()` | **87–146** | Smart table parsing |
| `pdf_extractor_withnotes.py` | `extract_all_attributes()` | **293–326** | Annotated PDF extractor |
| `pdf_extractor_withnotes.py` | `extract_income_statement_from_pdf()` | **1642–1728** | Advanced page-level statement finder |
| `pdf_extractor_withnotes.py` | `locate_income_statement_pages()` | **1577–1640** | Contents-page → statement page |
| `consolidate_metrics.py` | (entire file) | — | Earlier merge script |
| `show_pl_table.py` | (entire file) | — | Debug: display parsed tables |
| `debug_json.py` | (entire file) | — | Debug: inspect JSON structure |

---

## Output Files — Where They Are Written in Code

| Output file | Created by | File | Lines |
|-------------|-----------|------|-------|
| `{stem}.json` | PDF extraction | `archive/pdf_extractor.py` | **676–677** |
| `{stem}_pl.txt` | PDF extraction | `archive/pdf_extractor.py` | **679–696** |
| `pl_metrics_cleaned/{name}_metrics.json` | P&L extraction | `extract_pl_metrics_v2.py` | **1045–1047** |
| `pl_metrics_cleaned/pl_metrics_summary.csv` | P&L extraction | `extract_pl_metrics_v2.py` | **1050–1055** |
| `pl_metrics_cleaned/all_pl_metrics.json` | P&L extraction | `extract_pl_metrics_v2.py` | **1057–1059** |
| `pl_metrics_cleaned/audit_mismatches.json` | Audit | `audit_pl_metrics.py` | **74–77** |
| `pl_metrics_cleaned/pl_metrics_review.csv` | Review | `create_pl_review.py` | **48–79** |
| `pl_metrics_cleaned/all_pl_metrics_final.json` | Consolidate | `consolidate_final.py` | **84–85** |
| `pl_metrics_cleaned/profit_shifting_analysis.json` | Analysis | `analyze_profit_shifting.py` | **115–117** |
| `pl_metrics_cleaned/profit_shifting_indicators.csv` | Analysis | `analyze_profit_shifting.py` | **120–156** |
| `directors_output/directors_extracted.json` | Directors | `archive/extract_directors.py` | **90–92** |
| `directors_output/{name}_directors.txt` | Directors | `archive/extract_directors.py` | **95–107** |

---

## Concept → Code Map (Research Questions)

Use this when your professor asks *"where is X implemented?"*

| Research / technical question | Go to |
|------------------------------|-------|
| How does a PDF become JSON? | `archive/pdf_extractor.py` **291–324**, **669–677** |
| How is the P&L table sliced to `_pl.txt`? | `archive/pdf_extractor.py` **220–271**, **679–696** |
| How do we find the income statement in noisy OCR text? | `extract_pl_metrics_v2.py` **261–358** |
| How do we handle two-year column layouts? | `extract_pl_metrics_v2.py` **471–548**, **589–640** |
| How do we fix OCR label typos? | `extract_pl_metrics_v2.py` **195–214** |
| How do we avoid picking page numbers as turnover? | `extract_pl_metrics_v2.py` **12–44** (year filter), **949** (`min_abs=500`) |
| How do we parse `(1,234)` as negative? | `extract_pl_metrics_v2.py` **147–157** |
| What keywords find Turnover? | `extract_pl_metrics_v2.py` **949** |
| What keywords find Operating Profit? | `extract_pl_metrics_v2.py` **956** |
| What keywords find Profit Before Tax? | `extract_pl_metrics_v2.py` **963–964** |
| What keywords find Net Profit/Loss? | `extract_pl_metrics_v2.py` **972–974** |
| How is extraction confidence scored? | `extract_pl_metrics_v2.py` **1015–1023** |
| How are profit-shifting red flags defined? | `analyze_profit_shifting.py` **69–90** |
| How is net profit margin calculated? | `analyze_profit_shifting.py` **65–66** |
| How do we validate extraction vs ground truth? | `audit_pl_metrics.py` **32–64** |
| How is data completeness measured? | `create_pl_review.py` **23–26** |
| How are directors extracted from PDF text? | `archive/pdf_extractor.py` **327–507** |
| How is "Principal Activity" section found? | `archive/extract_principal_activity.py` **22–38** |
| What OCR corrections are applied to narrative text? | `archive/ocr_cleaner.py` **10–90** |
| Where is the ChatGPT development note? | `archive/scripts/extract_cleaned.py` (search for `CHATGPT`) or see `TECHNICAL_IMPLEMENTATION.md` §2.1 |

---

## Guardrail Layers → Exact Lines

The 4-layer guardrail system described in `TECHNICAL_IMPLEMENTATION.md` maps to these code locations:

| Layer | Description | Primary code location |
|-------|-------------|----------------------|
| **Layer 1** | P&L heading detection | `extract_pl_metrics_v2.py` **234–238** (`STATEMENT_HEADING_RE`), **261–358** (`find_best_statement_block`) |
| **Layer 2** | Row label density (turnover, operating profit, etc.) | `extract_pl_metrics_v2.py` **305–319** (scoring), **727–768** (`find_income_statement_start`) |
| **Layer 3** | Reject prose / balance sheet / auditor sections | `extract_pl_metrics_v2.py` **297–303**, **771–786** (`is_narrative_line`) |
| **Layer 4** | Score all candidates; pick best | `extract_pl_metrics_v2.py` **284–328** (best_score loop) |
| **Prototype (archive)** | Full 4-layer in one function | `archive/scripts/extract_cleaned.py` **68–293** (`find_pl_table_section`) |

---

## Jupyter Notebooks

| Notebook | Purpose |
|----------|---------|
| `sample/P_and_L_Extraction_Results.ipynb` | Interactive validation; cross-reference directors + metrics |
| `sample/pdf_dataframe.ipynb` | DataFrame-based analysis of extraction results |

*(Notebooks do not have fixed line numbers — open in Jupyter/Cursor to inspect cells.)*

---

## Example: Tracing One Company End-to-End

**Company:** `138763_2021 account` (ArcRoyal)

| Stage | File to open | Lines | What you will see |
|-------|-------------|-------|-------------------|
| Source PDF | `138763_2021 account.pdf` | — | Original filing |
| Extracted JSON | `138763_2021 account.json` | — | Full `text.full_text`, metadata |
| P&L text slice | `138763_2021 account_pl.txt` | — | OCR text including statement |
| Metric extraction logic | `extract_pl_metrics_v2.py` | **883–920** | Loads JSON companion + `_pl.txt` |
| Statement block parse | `extract_pl_metrics_v2.py` | **643–724** | Table → 4 numbers |
| Output | `pl_metrics_cleaned/138763_2021 account_pl_metrics.json` | — | Final extracted values + `raw_data` |
| Red-flag check | `analyze_profit_shifting.py` | **64–90** | Margin rules applied to this record |

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| [`README.md`](README.md) | Full workflow guide, architecture, how to run |
| [`TECHNICAL_IMPLEMENTATION.md`](TECHNICAL_IMPLEMENTATION.md) | Methodology, guardrails theory, LLM usage notes |

---

*DoubleIrishResearch — Villanova University. All line numbers refer to the codebase as of the last update to this index.*
