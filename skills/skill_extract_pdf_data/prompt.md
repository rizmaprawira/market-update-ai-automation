# Prompt: EKSTRAK DATA DARI PDF

## Task

Extract complete financial data from a PDF report into structured JSON format.

## Input

- **PDF file:** `{COMPANY_DIR}/laporan_keuangan.pdf`
- **Output directory:** `{COMPANY_DIR}/`

## Output

Save to: `{COMPANY_DIR}/{PREFIX}_raw.json`

## Requirements

Read the entire PDF and extract **all** financial data into the following JSON structure:

```json
{
  "extraction_metadata": {
    "pdf_filename": "laporan_keuangan.pdf",
    "extracted_at": "ISO 8601 timestamp",
    "extraction_status": "complete | partial | failed"
  },
  "company_info": {
    "name": "nama lengkap perusahaan",
    "jenis_asuransi": "Asuransi Umum | Asuransi Jiwa | Reasuransi",
    "reporting_period": "periode laporan",
    "currency": "IDR (Juta Rupiah) atau lainnya",
    "report_date": "tanggal laporan dirilis"
  },
  "balance_sheet": {
    "assets": {
      "investments": { /* detail semua jenis investasi */ },
      "non_investments": { /* detail kas, tagihan, aset lain */ },
      "total_assets": { "2026": 775667, "2025": 567941 }
    },
    "liabilities_and_equity": {
      "liabilities": { /* detail utang, cadangan teknis */ },
      "equity": { /* detail modal, agio, laba ditahan */ }
    }
  },
  "income_statement": {
    "underwriting_results": { /* premi bruto, premi netto, hasil underwriting */ },
    "investment_results": { /* hasil investasi */ },
    "operating_expenses": { /* beban usaha */ },
    "net_income": { /* laba rugi komprehensif */ }
  },
  "financial_ratios": {
    "solvency_ratios": { /* tingkat solvabilitas, MMBR */ },
    "liquidity_ratios": { /* rasio likuiditas */ },
    "other_ratios": { /* semua ratio lainnya */ }
  },
  "governance": {
    "board_of_directors": { /* dewan komisaris dan direksi */ },
    "shareholders": [ /* daftar pemegang saham */ ]
  },
  "notes_and_observations": [
    "observasi penting dari laporan",
    "perubahan signifikan vs tahun lalu"
  ],
  "extraction_notes": {
    "sections_found": ["balance_sheet", "income_statement", "financial_ratios"],
    "sections_not_found": [],
    "parsing_issues": [],
    "missing_fields": {
      "field_name": "reason why not found in PDF"
    }
  }
}
```

## Important

- Extract **SEMUA** data finansial, bukan hanya key metrics
- Dokumentasikan di `extraction_notes.sections_found`: section mana saja yang DITEMUKAN
- Dokumentasikan di `extraction_notes.sections_not_found`: section yang TIDAK DITEMUKAN
- Dokumentasikan di `extraction_notes.missing_fields`: field individual yang tidak ada di mana section mereka ditemukan
- File JSON HARUS disimpan bahkan jika data tidak lengkap

---

For full context and complete prompt, see `docs/PROMPT_TEMPLATES.md`.
