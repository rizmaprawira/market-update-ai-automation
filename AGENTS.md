# AGENTS — Codex Runtime Guardrails (v3)

## Objective
For each company URL and target period, produce contract-compliant artifacts in `data/YYYY-MM/{company_snake_case}/` and append valid rows to `database_konsolidasi.csv`.

## Required Outputs per Company
- `laporan_keuangan.pdf`
- `{company_snake_case}_raw.json`
- `{company_snake_case}_row.csv`
- `status.txt`

## CSV Contract (Strict)
- Pipe-delimited (`|`)
- Exactly 2 data rows, no header
- Exactly 12 columns per row
- Row 1 period must be current `YYYY-MM`
- Row 2 period must be prior `YYYY-1-MM`
- Use `N/A` only when field is truly unavailable

Schema:
`periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas`

## Status Contract
`status.txt` must contain exactly one of:
- `BERHASIL`
- `PARSIAL`
- `TIDAK_DITEMUKAN`
- `GAGAL`

Rules:
- `BERHASIL`: CSV valid and no `N/A`
- `PARSIAL`: CSV valid but has at least one `N/A`
- `TIDAK_DITEMUKAN`: report for target period unavailable
- `GAGAL`: technical/parsing/output contract failure

## Data Integrity Rules
- Do not hallucinate numbers.
- If a value is missing, write `N/A` and explain in `extraction_notes.missing_fields`.
- Always produce JSON, including failure/partial scenarios.
- Do not append invalid or duplicate rows to consolidated CSV.

## Runtime Defaults
- Script entrypoint: `scripts/akuisisi_data_v3.sh`
- Prompt template: `docs/codex_exec_prompt_v3.txt`
- Model default: `gpt-5.5`
- Approval default: `never`
- Sandbox default: `workspace-write`
