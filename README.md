# Market Update Automation (Codex Optimized) — Indonesian Insurance Financial Pipeline

Automated workflow for acquiring, extracting, and consolidating monthly financial reports from Indonesian insurance and reinsurance companies.

## Current Default

- Runtime default: `scripts/akuisisi_data_v3.sh`
- Agent runner: `codex exec` (non-interactive)
- Prompt template source of truth: `docs/codex_exec_prompt_v3.txt`
- Legacy scripts (`v1`/`v2`) are kept for reference only.

## Goal

Acquire financial reports from **125+ companies** → extract & standardize data → produce consolidated CSV ready for analysis & visualization.

## Prerequisites

- Codex CLI installed and authenticated (`codex --version`)
- Bash shell
- curl or wget
- Optional: pdftotext (poppler-utils)

## Quick Start

### Test Run (1 Company)

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/test_companies.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 0
```

### Prototype Run (8 Companies)

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/link_reasuransi.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 5
```

### Production Run (125+ Companies)

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/companies.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 5
```

Resume if interrupted:

```bash
bash scripts/akuisisi_data_v3.sh --YYYY 2026 --MM 04 --companies config/companies.txt --resume
```

## CLI Flags (v3)

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/companies.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 5 \
  --resume \
  --fail-fast
```

- `--YYYY` (required): target year, 4 digits
- `--MM` (required): target month, `01..12`
- `--companies` (required): input URL list (one URL per line)
- `--model` (optional): Codex model (default `gpt-5.3-codex`)
- `--approval-policy` (optional): `untrusted|on-request|on-failure|never` (default `never`)
- `--sandbox` (optional): `read-only|workspace-write|danger-full-access` (default `workspace-write`)
- `--delay` (optional): delay seconds between URLs (default `5`)
- `--resume` (optional): skip URLs already marked `SUCCESS` in checkpoint
- `--fail-fast` (optional): stop immediately on first permanent failure

## Output Contract (v3)

`data/YYYY-MM/`
- `database_konsolidasi.csv`
- `log.txt`
- `.checkpoint_YYYY-MM.txt`
- `summary.md`
- `{company_snake_case}/`

`data/YYYY-MM/{company_snake_case}/`
- `laporan_keuangan.pdf`
- `{company_snake_case}_raw.json`
- `{company_snake_case}_row.csv`
- `status.txt` (`BERHASIL|PARSIAL|TIDAK_DITEMUKAN|GAGAL`)

## Directory Structure

```text
market-update-automation-codex/
├── README.md
├── AGENTS.md
├── config/
├── scripts/
│   ├── akuisisi_data_v3.sh        # default runner
│   ├── akuisisi_data_v2.sh        # legacy reference
│   └── akuisisi_data.sh           # legacy reference
├── docs/
│   ├── SETUP.md
│   ├── plan_v3.md
│   ├── TROUBLESHOOTING_CODEX_V3.md
│   ├── codex_exec_prompt_v3.txt   # v3 prompt template (default)
│   └── claude_code_prompt.txt     # legacy prompt template
├── data/
├── analysis/
├── skills/
└── knowledge/
```

## Documentation

- Setup: `docs/SETUP.md`
- v3 execution contract: `docs/plan_v3.md`
- Codex troubleshooting: `docs/TROUBLESHOOTING_CODEX_V3.md`
- Prompt template (default): `docs/codex_exec_prompt_v3.txt`

## Legacy Notes

- `v1` and `v2` scripts/docs are retained for audit and comparison.
- `.claude/` files are retained as historical artifacts and are not used by v3 Codex default flow.
