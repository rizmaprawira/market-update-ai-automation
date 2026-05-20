# Architecture — Financial Data Pipeline

## Overview

The market-update-automation project is an **automated workflow** to acquire, extract, and consolidate monthly financial reports from Indonesian insurance/reinsurance companies.

### High-Level Goal

Acquire financial reports from 125+ companies → extract and standardize data into a consolidated CSV → ready for analysis and visualization.

### Current Phase

Testing and validating the workflow with 8 reinsurance companies to ensure extraction quality and N/A transparency before scaling to the full 125.

---

## System Components

### 1. Orchestration Script: `scripts/akuisisi_data_v2.sh`

Main driver script that iterates through a list of company URLs, invokes Claude for each company, and manages output/checkpoints.

**Usage:**
```bash
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04
bash scripts/akuisisi_data_v2.sh --YYYY 2025 --MM 12 --resume --delay 10
```

**Available flags:**

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--YYYY` | Yes | — | Year (4 digits) |
| `--MM` | Yes | — | Month (2 digits, 01–12) |
| `--resume` | No | false | Skip URLs already in checkpoint (resume capability) |
| `--delay N` | No | 5 | Delay in seconds between companies |
| `--companies FILE` | No | config/companies.txt | Path to URL list file |
| `--fail-fast` | No | false | Stop on first error (don't process remaining URLs) |

### 2. Input: Company URLs

**File:** `config/companies.txt`

Simple text file, one URL per line. Lines starting with `#` (comments) and empty lines are ignored.

```
# Reasuransi
https://inare.co.id/en/report/
https://www.indonesiare.co.id/id/investor-relations/financial-report

# Asuransi Umum
https://www.orionre.id/id/publikasi.html
# ... (125+ URLs total)
```

### 3. Execution Flow

```
Input: config/companies.txt (URL per line)
  ↓
akuisisi_data_v2.sh loops over each URL
  ↓
For each URL:
  a. Inject prompt into Claude CLI (with URL, period, output path)
  b. Claude:
     - Finds report on website
     - Downloads PDF
     - Extracts full JSON (balance sheet, income statement, ratios, governance, etc.)
     - Transforms JSON to 2-row CSV (current year + prior year)
     - Writes status file (BERHASIL | PARSIAL | TIDAK_DITEMUKAN | GAGAL)
  c. akuisisi_data_v2.sh:
     - Validates CSV format (12 columns, correct period, etc.)
     - Appends rows to consolidated CSV
     - Records checkpoint (SUCCESS or FAILED)
  ↓
Output:
  - data/YYYY-MM/database_konsolidasi.csv (all 125+ companies)
  - data/YYYY-MM/{company_name}/ (per-company: JSON, CSV row, status, PDF)
  - data/YYYY-MM/.checkpoint_YYYY-MM.txt (for resume capability)
```

### 4. Claude Prompt (Embedded in Script)

The prompt template is in `docs/PROMPT_TEMPLATES.md`. Five required steps:

1. **Find Report** — Navigate website, locate monthly report for target period
2. **Download PDF** — Save to per-company output directory
3. **Extract Full JSON** — Parse entire PDF into structured JSON (complete financial data)
4. **Transform to CSV** — Extract 12 key metrics, create 2-row CSV (current + prior year)
5. **Write Status** — Create status file (BERHASIL/PARSIAL/TIDAK_DITEMUKAN/GAGAL)

### 5. Output Structure

```
data/
├── 2026-04/
│   ├── database_konsolidasi.csv          (consolidated: all companies, 2 rows each)
│   ├── log.txt                            (timestamped run log)
│   ├── summary.md                         (human-readable summary)
│   ├── .checkpoint_2026-04.txt            (resume checkpoint)
│   ├── plots/                             (generated charts, if analyzed)
│   │
│   ├── pt_indoperkasa_suksesjaya_reasuransi/
│   │   ├── inare_raw.json                 (full extracted JSON)
│   │   ├── inare_row.csv                  (2-row CSV for this company)
│   │   ├── status.txt                     (BERHASIL | PARSIAL | ...)
│   │   ├── laporan_keuangan.pdf          (downloaded PDF)
│   │   └── ...
│   │
│   ├── pt_orion_reasuransi_indonesia/
│   │   ├── orion_re_raw.json
│   │   ├── orion_re_row.csv
│   │   ├── status.txt
│   │   └── ...
│   │
│   └── ... (125+ company directories)
│
├── 2026-03/
├── 2026-02/
└── 2026-01/
```

---

## Data Formats

### CSV Format

**Delimiter:** Pipe (`|`)  
**Numbers:** Thousands separator is POINT (`.`), no currency symbols or units

**Schema (12 columns):**

```
periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
```

**Example row:**
```
2026-04|Reasuransi|PT Tugu Reasuransi Indonesia|1.234.567|567.890|123.456|654.321|543.210|98.765|-45.678|125.5|89.2
```

### JSON Schema (data_ekstrak.json)

Complete extraction of all financial data from the PDF:

```json
{
  "extraction_metadata": {
    "pdf_filename": "...",
    "extracted_at": "ISO 8601 timestamp",
    "extraction_status": "complete | partial | failed"
  },
  "company_info": { ... },
  "balance_sheet": {
    "assets": { "investments": {...}, "non_investments": {...}, "total_assets": {...} },
    "liabilities_and_equity": { "liabilities": {...}, "equity": {...} }
  },
  "income_statement": {
    "underwriting_results": { ... },
    "investment_results": { ... },
    "operating_expenses": { ... },
    "net_income": { ... }
  },
  "financial_ratios": {
    "solvency_ratios": { ... },
    "liquidity_ratios": { ... }
  },
  "governance": {
    "board_of_directors": { ... },
    "shareholders": [ ... ]
  },
  "notes_and_observations": [ ... ],
  "extraction_notes": {
    "sections_found": [ ... ],
    "sections_not_found": [ ... ],
    "parsing_issues": [ ... ],
    "missing_fields": { "field_name": "reason why N/A", ... }
  }
}
```

### Status Values

| Status | Meaning | Example |
|--------|---------|---------|
| **BERHASIL** | Both rows (current + prior year) fully populated, no N/A fields | All 9 metrics found and extracted |
| **PARSIAL** | Data extracted but 1+ metric is N/A (documented in extraction_notes) | 7 of 9 metrics found; 2 marked N/A |
| **TIDAK_DITEMUKAN** | Report for target month/year not published on website | Period 2026-04 not yet released |
| **GAGAL** | Technical error (PDF corrupted, parsing failed, network error, etc.) | PDF download timeout, malformed JSON |

---

## Key Features

### Resume Capability

```bash
# If interrupted mid-run, restart with --resume flag
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --resume
# Will skip URLs already in .checkpoint_2026-04.txt
```

Checkpoint file format:
```
SUCCESS:https://inare.co.id/en/report/
SUCCESS:https://www.indonesiare.co.id/...
FAILED:https://some_url_with_error
```

### N/A Transparency

When a metric is missing (not found in PDF):
1. Mark as `N/A` in CSV
2. Document reason in `extraction_notes.missing_fields` in JSON
3. Auto-downgrade status from BERHASIL to PARSIAL

### Validation

The script validates each company's output CSV before appending to consolidated CSV:
- File exists
- Exactly 12 pipe-delimited columns
- Period field matches expected `YYYY-MM` format

---

## Tools & Dependencies

### Required

- **Claude CLI** — `claude` command must be installed and authenticated
- **Bash** — POSIX shell for script execution
- **curl or wget** — for PDF downloads (embedded in prompt)

### Recommended

- **pdftotext** (poppler-utils) — for reliable PDF text extraction

### Claude Code Configuration

File: `.claude/settings.json`

```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "WebFetch"]
  }
}
```

This pre-approves tool requests so the script runs non-interactively.

---

## Next Steps

### Phase: Testing (Current)

- ✅ Validate workflow with 8 test companies
- ✅ Confirm extraction accuracy and N/A transparency
- Refine company directory naming (currently 001_https_/, will be renamed to full company names)
- Prepare for scaling

### Phase: Scaling

- Onboard 125+ companies in `config/companies.txt`
- Run monthly acquisition workflow
- Monitor for extraction quality and failures

### Phase: Analysis

- Use `analysis/plot_metrics_reasuransi.py` to generate visualizations
- Build downstream dashboards/reports from consolidated CSV

---

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for common issues and solutions.
