# Prompt: TRANSFORMASI JSON KE CSV

## Task

Transform extracted JSON into a 2-row CSV with 12 key metrics (current year + prior year).

## Input

- **JSON file:** `{COMPANY_DIR}/{PREFIX}_raw.json`

## Output

Save to: `{COMPANY_DIR}/{PREFIX}_row.csv`

## Requirements

Extract 12 key metrics from the JSON and create **exactly 2 CSV rows** (no header):

**Row 1:** Current year ({TAHUN}-{BULAN}) values  
**Row 2:** Prior year ({TAHUN-1}-{BULAN}) values

### CSV Format

- **Delimiter:** PIPE (`|`)
- **Numbers only:** Remove units ("juta rupiah", "%", etc.)
- **Thousands separator:** POINT (`.`) — e.g., "7.288.332"
- **Negative values:** Include minus sign (e.g., "-45.678")

### 12 Metrics Definition

Extract from corresponding JSON sections:

1. **aset** ← balance_sheet.assets.total_assets
2. **ekuitas** ← balance_sheet.liabilities_and_equity.equity.total_equity
3. **premi_penutupan_tidak_langsung** ← income_statement.underwriting_results (or N/A if missing)
4. **premi_bruto** ← income_statement.underwriting_results
5. **pendapatan_premi** ← income_statement.underwriting_results (net/earned premium)
6. **hasil_underwriting** ← income_statement.underwriting_results
7. **laba_rugi_komprehensif** ← income_statement.net_income (include negative if loss)
8. **rasio_solvabilitas** ← financial_ratios.solvency_ratios
9. **rasio_likuiditas** ← financial_ratios.liquidity_ratios

### CSV Structure

```
{TAHUN}-{BULAN}|{jenis_asuransi}|{nama_perusahaan}|{aset}|{ekuitas}|{premi_penutupan_tl}|{premi_bruto}|{pendapatan_premi}|{hasil_uw}|{laba_rugi}|{rasio_solv}|{rasio_likuid}
{TAHUN-1}-{BULAN}|{jenis_asuransi}|{nama_perusahaan}|{aset}|{ekuitas}|{premi_penutupan_tl}|{premi_bruto}|{pendapatan_premi}|{hasil_uw}|{laba_rugi}|{rasio_solv}|{rasio_likuid}
```

## Handling N/A

- If a metric **is not found** in the JSON section → use `N/A` in the CSV cell
- If a metric **is found but partial** → use `N/A` for missing components
- Use N/A only as a last resort; extract what you can

## Important

- **Exactly 2 rows** — no header, no extra rows
- **Exactly 12 columns** separated by pipe (`|`)
- **All values numeric** except periode, jenis_asuransi, nama_perusahaan, and N/A
- Do not include currency symbols or units in numeric fields

---

For full context and complete prompt, see `docs/PROMPT_TEMPLATES.md`.
