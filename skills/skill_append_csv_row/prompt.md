# Prompt: TULIS STATUS FILE & APPEND CSV

## Task

Determine extraction quality and write status file. Append CSV rows to consolidated CSV.

## Inputs

- **CSV file:** `{COMPANY_DIR}/{PREFIX}_row.csv` (2 rows)
- **JSON file:** `{COMPANY_DIR}/{PREFIX}_raw.json` (for extraction_notes)
- **Consolidated CSV:** `{OUTPUT_DIR}/database_konsolidasi.csv`

## Outputs

- **status.txt:** Single line, one of: BERHASIL | PARSIAL | TIDAK_DITEMUKAN | GAGAL
- **Updated database_konsolidasi.csv:** Append 2 rows (if applicable)

## Status Determination

### Step 1: Count N/A fields in the 2-row CSV

```bash
grep -o "N/A" {PREFIX}_row.csv | wc -l
```

- **0 N/A fields** → BERHASIL
- **1+ N/A fields** → PARSIAL
- **Report not published** → TIDAK_DITEMUKAN
- **Technical error** → GAGAL

### Step 2: Write status.txt

Create file: `{COMPANY_DIR}/status.txt`

Content: **exactly one word** (no spaces, no newline characters except at end)

```
BERHASIL
```

or

```
PARSIAL
```

or

```
TIDAK_DITEMUKAN
```

or

```
GAGAL
```

### Step 3: Append to Consolidated CSV

**First run only:** Create header if `database_konsolidasi.csv` does not exist:

```
periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
```

**Always (if BERHASIL or PARSIAL):** Append both rows from `{PREFIX}_row.csv` to `database_konsolidasi.csv`

**Do NOT append** if status is:
- TIDAK_DITEMUKAN (report missing)
- GAGAL (technical error)

## Important Rules

- **status.txt:** Exactly **one word**, no extra text
- **N/A transparency:** Already documented in extraction_notes.missing_fields in the JSON
- **Both rows:** Append current year + prior year (or skip both if GAGAL/TIDAK_DITEMUKAN)
- **CSV integrity:** Ensure 12 columns, proper delimiters, line endings

## Example

**Input CSV (`tugu_re_row.csv`):**
```
2026-04|Reasuransi|PT Tugu Reasuransi Indonesia|1234567|567890|123456|654321|543210|98765|-45678|125.5|89.2
2025-04|Reasuransi|PT Tugu Reasuransi Indonesia|1000000|500000|N/A|500000|450000|75000|-20000|120.0|85.0
```

**N/A count:** 1 field (one N/A in 2×12 cells)  
**Status:** PARSIAL  
**Action:** Append both rows to database_konsolidasi.csv

---

For full context and complete prompt, see `docs/PROMPT_TEMPLATES.md`.
