# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Market Update Automation (Codex Optimized)** — Automated financial report acquisition, extraction, and consolidation for 125+ Indonesian insurance and reinsurance companies.

### Goal
Acquire monthly financial reports → extract standardized data → produce consolidated CSV ready for analysis.

### Current Coverage
- **Reasuransi** (Reinsurance): 8 companies
- **Asuransi Jiwa** (Life Insurance): 48 companies
- **Asuransi Umum** (General Insurance): 71 companies

---

## Quick Start Commands

### Main Orchestrator (All Three Categories)
```bash
./scripts/akuisisi_data/akuisisi_data_all.sh --yyyy 2026 --mm 03 [options]
```

**Required flags:**
- `--yyyy <year>`: 4-digit year (e.g., 2026)
- `--mm <month>`: 2-digit month (01–12)

**Useful optional flags:**
- `--resume`: Skip already-downloaded PDFs/extracted metrics
- `--timeout <sec>`: Timeout per company (default 30)
- `--delay <sec>`: Delay between companies (default 2)
- `--fail-fast`: Stop on first failure
- `--dry-run`: Test without actual download/conversion
- `--discover-only`: Discover reports without downloading
- `--output-root <dir>`: Custom output directory (default: `data`)

### Category-Specific Runners
```bash
# Reinsurance only
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03

# Life insurance only
./scripts/akuisisi_data/akuisisi_data_jiwa.sh --yyyy 2026 --mm 03

# General insurance only
./scripts/akuisisi_data/akuisisi_data_umum.sh --yyyy 2026 --mm 03
```

### Legacy Codex v3 (Deprecated, Reference Only)
```bash
bash scripts/workflow_with_ai/akuisisi_data_v3.sh \
  --YYYY 2026 --MM 04 \
  --companies config/link_reasuransi.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 5
```

---

## Architecture & Data Flow

### Execution Phases

1. **Discovery** — Locate financial reports on company websites
2. **Download** — Fetch PDFs to `data/YYYY-MM/raw_pdf/{category}/{company_id}/`
3. **Text Extraction** — Convert PDFs to text with OCR support via `pdftotext`
4. **Key Metrics Extraction** — Parse text using company-specific Python scripts, output JSON + CSV
5. **Consolidation** — Validate and append rows to `database_konsolidasi.csv`

### Directory Structure

```
scripts/
├── akuisisi_data/
│   ├── akuisisi_data_all.sh              # Orchestrator (all 3 categories)
│   ├── akuisisi_data_reasuransi.sh       # Reinsurance runner
│   ├── akuisisi_data_jiwa.sh             # Life insurance runner
│   ├── akuisisi_data_umum.sh             # General insurance runner
│   ├── reasuransi/
│   │   ├── download_reasuransi.py        # Per-company downloaders
│   │   ├── *_key_metric_helpers.py       # Company-specific extractors
│   │   └── *_key_metrics_extractor.py
│   ├── asuransi_jiwa/
│   │   ├── download_asuransi_jiwa.py
│   │   ├── download_pt_*.py              # 48 company scripts
│   │   ├── _standardize_jiwa.py
│   │   ├── _downloader_base.py
│   │   └── _key_metric_helpers.py
│   ├── asuransi_umum/
│   │   ├── download_asuransi_umum.py
│   │   ├── download_pt_*.py              # 71 company scripts
│   │   └── _key_metric_helpers.py
│   └── utils/
│       ├── validate_input.sh
│       ├── setup.sh
│       └── cleanup.sh
├── utils/
└── workflow_with_ai/                     # Legacy Codex v3 (reference)
    ├── akuisisi_data_v3.sh
    ├── akuisisi_data_v2.sh
    └── akuisisi_data.sh

data/
├── YYYY-MM/
│   ├── database_konsolidasi.csv          # Consolidated output
│   ├── log.txt                           # Execution log
│   ├── summary.md                        # Human-readable summary
│   ├── .checkpoint_YYYY-MM.txt           # Resume checkpoint
│   ├── raw_pdf/                          # Downloaded PDFs
│   │   ├── reasuransi/
│   │   ├── asuransi_jiwa/
│   │   └── asuransi_umum/
│   ├── pdf_text/                         # Extracted text from PDFs
│   └── metrics/                          # JSON + CSV key metrics
│       ├── reasuransi/
│       ├── asuransi_jiwa/
│       └── asuransi_umum/

config/
├── companies.txt                         # All 125+ company URLs (production)
├── link_reasuransi.txt                   # 8 reinsurance URLs (test)
└── test_companies.txt                    # 1 URL smoke test
```

---

## Output Contract

### Consolidated CSV: `database_konsolidasi.csv`

**Format:** Pipe-delimited (`|`), no header, exactly 2 rows per company (current month + prior month)

**Schema (12 columns):**
```
periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
```

**Example:**
```
2026-04|Reasuransi|PT Tugu Reasuransi Indonesia|1.234.567|567.890|123.456|654.321|543.210|98.765|-45.678|125.5|89.2
2026-03|Reasuransi|PT Tugu Reasuransi Indonesia|1.200.000|560.000|120.000|650.000|540.000|95.000|-40.000|124.0|88.5
```

**Numbers:** Thousands separator is POINT (`.`), no currency symbols

### Per-Company Status: `data/YYYY-MM/{company_id}/{company_id}_status.txt`

Must contain exactly one of:
- `BERHASIL` — Complete extraction, no N/A values
- `PARSIAL` — Extraction valid but has ≥1 N/A value
- `TIDAK_DITEMUKAN` — Report for target period not published
- `GAGAL` — Technical error (PDF corrupt, parsing failed, etc.)

### Per-Company Metrics: `data/YYYY-MM/metrics/{category}/{company_id}/`
- `{company_id}_raw.json` — Full extracted JSON (all financial sections)
- `{company_id}_row.csv` — 2-row CSV extract for this company
- `{company_id}_status.txt` — Status file

---

## Key Architectural Patterns

### 1. Company-Specific Downloaders

Each company has a dedicated Python script (e.g., `download_pt_ajb_bumiputera_1912.py`) that:
- Knows the company's specific website layout
- Handles dynamic content (JavaScript-heavy sites) via Playwright
- Implements retry logic and anti-bot detection
- Downloads the PDF to a standardized path

**Location:** `scripts/akuisisi_data/{category}/download_pt_*.py`

### 2. Key Metrics Extraction

Company-specific helper scripts extract 12–13 key financial metrics from PDF text:
```python
# Example metrics for reasuransi (13 fields):
- periode, jenis_asuransi, nama_perusahaan
- aset, ekuitas, premi_penutupan_tidak_langsung
- premi_bruto, pendapatan_premi, hasil_underwriting
- laba_rugi_komprehensif, rasio_solvabilitas, rasio_likuiditas
```

**Location:** `scripts/akuisisi_data/{category}/*_key_metric_helpers.py`

### 3. Data Upsert Pattern

Once metrics are extracted as JSON + CSV:
1. Validate CSV format (12 columns, pipe-delimited)
2. Check period matches expected YYYY-MM
3. Append to `database_konsolidasi.csv` only if valid
4. Log success/failure in checkpoint for resume capability

### 4. Resume Capability

`.checkpoint_YYYY-MM.txt` stores status of each company URL:
```
SUCCESS:{company_id}
FAILED:{company_id}
PENDING:{company_id}
```

Running with `--resume` skips companies already marked SUCCESS or FAILED.

---

## Development Tips

### Testing a Single Company

```bash
# Run just one reinsurance company's downloader
python3 scripts/akuisisi_data/reasuransi/download_pt_indoperkasa_suksesjaya_reasuransi.py \
  --year 2026 --month 3 \
  --output-root data

# Test key metrics extraction
python3 scripts/akuisisi_data/reasuransi/pt_indoperkasa_suksesjaya_reasuransi_key_metrics_extractor.py \
  --input-pdf data/2026-03/raw_pdf/reasuransi/pt_indoperkasa_suksesjaya_reasuransi/ \
  --output-json data/2026-03/metrics/reasuransi/pt_indoperkasa_suksesjaya_reasuransi/pt_indoperkasa_suksesjaya_reasuransi_raw.json \
  --output-csv data/2026-03/metrics/reasuransi/pt_indoperkasa_suksesjaya_reasuransi/pt_indoperkasa_suksesjaya_reasuransi_row.csv
```

### Checking Extraction Quality

```bash
# View consolidated database
head -20 data/2026-03/database_konsolidasi.csv

# Check specific company's status
cat data/2026-03/metrics/reasuransi/pt_indoperkasa_suksesjaya_reasuransi/pt_indoperkasa_suksesjaya_reasuransi_status.txt

# View extraction notes
cat data/2026-03/metrics/reasuransi/pt_indoperkasa_suksesjaya_reasuransi/pt_indoperkasa_suksesjaya_reasuransi_raw.json | jq '.extraction_notes'

# Check run log
tail -100 data/2026-03/log.txt
```

### Debugging Playwright Issues

Company scripts use Playwright for dynamic sites. If a download fails:
1. Check `log.txt` for Playwright-specific errors (timeouts, element not found, etc.)
2. Review the company-specific script to understand which elements it waits for
3. May need to adjust CSS selectors or wait conditions if the website layout changed

Common patterns in scripts:
```python
# Wait for element and extract text
page.wait_for_selector("table.financial-data")

# Click download link and save PDF
page.click("a[href*='report.pdf']")

# Handle dynamic dropdowns
page.select_option("#month-selector", "03")
```

---

## Environment & Dependencies

### Required
- **Bash** shell (macOS/Linux)
- **Python 3.10+** with mamba/conda for isolated environments
- **pdftotext** (poppler-utils) for PDF text extraction

### Python Dependencies (in `market_update` mamba environment)
Pre-installed in the default mamba environment. Key packages:
- `playwright` — Browser automation for dynamic sites
- `pandas` — CSV/JSON handling
- `requests` — HTTP downloads
- `beautifulsoup4` — HTML parsing
- `pillow` — Image processing for OCR

### Mamba Environment

Project uses a `market_update` mamba environment with all dependencies pre-installed.

**Using the environment:**
```bash
# Activate
mamba activate market_update

# List installed packages
mamba list

# Install additional package (rare)
mamba install -c conda-forge <package>

# Deactivate
mamba deactivate
```

**Cache & Performance:**
- Scripts may create mamba lock files during parallel downloads
- Default cache: `/tmp/market-update-mamba-cache`
- Override with `--mamba-cache-home <dir>` if needed

---

## Important Notes

### N/A Handling

When a metric is missing from the PDF:
1. Mark field as `N/A` in CSV
2. Document reason in `extraction_notes.missing_fields` in JSON
3. Status auto-downgrades from BERHASIL to PARSIAL

**Do not hallucinate numbers.** Use `N/A` if truly unavailable.

### Legacy Code

- `scripts/workflow_with_ai/` — Codex v3 integration (deprecated, kept for reference)
- `.claude/` directory — Historical artifacts, not used by current workflow
- `archive/` — Old runs and legacy scripts from v1/v2

### Version History

- **v3** (Codex integration): `scripts/workflow_with_ai/akuisisi_data_v3.sh` — Uses `codex exec`
- **v2** (Claude Code integration): Reference only
- **v1** (Initial prototype): Reference only
- **Current** (2026-05+): Python-based orchestrator in `scripts/akuisisi_data/`

---

## Documentation Files

- `README.md` — Project overview and quick start
- `AGENTS.md` — Output contract for v3 Codex workflow
- `docs/ARCHITECTURE.md` — Detailed system design
- `docs/plan_v3.md` — Codex v3 execution flow (Indonesian)
- `docs/SETUP.md` — Initial setup instructions
- `docs/TROUBLESHOOTING.md` — Common issues and solutions
- `knowledge/` — Domain knowledge (insurance types, metrics, Indonesian language)
- `config/` — Company URL lists (by category)

---

## Common Issues & Solutions

### "pdftotext: command not found"
Install poppler-utils: `brew install poppler` (macOS) or `apt install poppler-utils` (Linux)

### Download timeout on slow websites
Increase timeout: `--timeout 60` (default 30s)

### Resume not skipping completed companies
Check `.checkpoint_YYYY-MM.txt` — URL must match exactly

### CSV validation fails
Check CSV has exactly 12 pipe-delimited columns and 2 rows
```bash
wc -l data/2026-03/metrics/*/pt_*/*_row.csv
```

### Playwright element not found errors
Website layout may have changed. Edit the company-specific downloader script to update CSS selectors
