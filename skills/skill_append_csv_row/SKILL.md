# Skill: Write Status File & Log

## Purpose

Create status file and append CSV rows to the consolidated consolidated CSV based on extraction quality.

## Inputs

- **{prefix}_row.csv:** 2-row CSV from skill_transform_json_to_csv
- **{prefix}_raw.json:** Extraction notes with N/A counts
- **database_konsolidasi.csv:** Main consolidated CSV (create if not exists)

## Outputs

- **status.txt:** Single status line (BERHASIL | PARSIAL | TIDAK_DITEMUKAN | GAGAL)
- **Updated database_konsolidasi.csv:** 2 rows appended (current + prior year)

## Status Codes

| Status | When | CSV Impact |
|--------|------|-----------|
| **BERHASIL** | All 12 metrics fully populated, zero N/A | Both rows appended |
| **PARSIAL** | Data exists but 1+ metric is N/A | Both rows appended (with N/A) |
| **TIDAK_DITEMUKAN** | Report for target period not available on website | No rows appended (skip) |
| **GAGAL** | Technical error (PDF download failed, parsing error) | No rows appended (skip) |

## Rules

1. **Count N/A fields** in the 2-row CSV
2. **If N/A count = 0** → BERHASIL
3. **If N/A count > 0** → PARSIAL
4. **If report missing** → TIDAK_DITEMUKAN (document in extraction_notes)
5. **If technical error** → GAGAL (document error in extraction_notes)

## CSV Consolidation

- **Header (first run):** periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
- **Append:** Add 2 rows from {prefix}_row.csv
- **File location:** `{OUTPUT_DIR}/database_konsolidasi.csv`

## Important

- **status.txt** must contain **exactly one word** (no extra whitespace)
- Do **not** include N/A transparency in status; PARSIAL covers all partial cases
- Append both rows (current + prior year) if status ≠ GAGAL and ≠ TIDAK_DITEMUKAN

## See Also

- `docs/PROMPT_TEMPLATES.md` — Full prompt template
- `skills/skill_transform_json_to_csv/` — Previous step (CSV transformation)
