# Skill: Transform JSON to CSV

## Purpose

Transform extracted JSON financial data into a 2-row CSV format (current year + prior year) with 12 key metrics.

## Inputs

- **{prefix}_raw.json:** Extracted financial data from skill_extract_pdf_data

## Outputs

- **{prefix}_row.csv:** 2 rows (current year + prior year), 12 pipe-delimited columns, pure numbers

## Format

**Schema (12 columns):**

```
periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
```

**Example:**
```
2026-04|Reasuransi|PT Tugu Reasuransi Indonesia|1234567|567890|123456|654321|543210|98765|-45678|125.5|89.2
2025-04|Reasuransi|PT Tugu Reasuransi Indonesia|1000000|500000|N/A|500000|450000|75000|-20000|120.0|85.0
```

## 12 Metrics

| # | Field | Source in JSON | Rules |
|---|-------|---|---|
| 1 | aset | balance_sheet.assets.total_assets | Current year value |
| 2 | ekuitas | balance_sheet.liabilities_and_equity.equity.total_equity | Current year value |
| 3 | premi_penutupan_tidak_langsung | income_statement.underwriting_results | Use N/A if not found |
| 4 | premi_bruto | income_statement.underwriting_results | — |
| 5 | pendapatan_premi | income_statement.underwriting_results | Net/earned premium |
| 6 | hasil_underwriting | income_statement.underwriting_results | — |
| 7 | laba_rugi_komprehensif | income_statement.net_income | Mark NEGATIVE if loss |
| 8 | rasio_solvabilitas | financial_ratios.solvency_ratios | — |
| 9 | rasio_likuiditas | financial_ratios.liquidity_ratios | — |

## Key Requirements

- **Pure numbers only** — remove units ("juta rupiah", "%", etc.)
- **Thousands separator:** POINT (`.`) not comma
- **Delimiter:** PIPE (`|`)
- **2 rows:** One for current year, one for prior year
- **N/A handling:** If field not found in JSON, use `N/A` in CSV and document in extraction_notes

## See Also

- `docs/PROMPT_TEMPLATES.md` — Full prompt template
- `skills/skill_extract_pdf_data/` — Previous step (extraction)
- `skills/skill_append_csv_row/` — Next step (status file)
