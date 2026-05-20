# Setup & Getting Started (Codex v3)

## Prerequisites

1. **Codex CLI** installed and authenticated
   ```bash
   which codex
   codex --version
   ```

2. **Bash** shell (macOS/Linux)
3. **curl** or **wget**
4. Optional: `pdftotext` (poppler-utils)

## Verify Codex CLI

Run a small non-interactive test:

```bash
printf 'Balas dengan satu kata: OK' | codex --ask-for-approval never exec --skip-git-repo-check --model gpt-5.5 --sandbox workspace-write -
```

If this command returns a normal text response, Codex CLI is ready for automation.

## Project Structure (Relevant for v3)

```text
scripts/akuisisi_data_v3.sh         # Main orchestrator (default)
docs/codex_exec_prompt_v3.txt       # Prompt template source of truth
data/YYYY-MM/                       # Period outputs
config/link_reasuransi.txt          # Prototype URL list
config/companies.txt                # Production URL list
```

## Make Scripts Executable

```bash
chmod +x scripts/*.sh
```

## Quick Start

### 1) Smoke test (1 URL)

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/test_companies.txt \
  --model gpt-5.5 \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 0
```

### 2) Prototype run (8 URLs)

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/link_reasuransi.txt \
  --model gpt-5.5 \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 5
```

### 3) Resume run

```bash
bash scripts/akuisisi_data_v3.sh --YYYY 2026 --MM 04 --companies config/link_reasuransi.txt --resume
```

## Validate Output

1. Check consolidated CSV:
   ```bash
   head -5 data/2026-04/database_konsolidasi.csv
   ```
2. Check run log:
   ```bash
   tail -50 data/2026-04/log.txt
   ```
3. Check per-company artifacts:
   ```bash
   ls data/2026-04/pt_tugu_reasuransi_indonesia/
   ```
4. Check checkpoint for resume:
   ```bash
   cat data/2026-04/.checkpoint_2026-04.txt
   ```

## Notes on Repository Mode

- Repo ini sengaja hasil duplicate konten tanpa `.git` dari repo sumber.
- Script v3 selalu menjalankan Codex dengan `--skip-git-repo-check` agar tetap kompatibel pada mode ini.

## Legacy

- `scripts/akuisisi_data.sh` (v1) dan `scripts/akuisisi_data_v2.sh` tetap tersedia sebagai referensi.
- Dokumen lama yang Claude-specific tidak dihapus untuk kebutuhan audit/historical comparison.
