# SUMMARY v3 — Codex Optimization Update

## Ringkasan
Workflow v3 tetap mempertahankan kontrak output `data/YYYY-MM`, namun runtime default kini dioptimalkan untuk Codex non-interaktif.

## Perubahan Utama

### 1) Runner v3 dipindah ke Codex
File: `scripts/akuisisi_data_v3.sh`
- Engine eksekusi: `claude --print` -> `codex exec`
- Default model: `gpt-5.5`
- Penambahan flag runtime:
  - `--approval-policy`
  - `--sandbox`
- Menjalankan `--skip-git-repo-check` agar kompatibel pada repo hasil duplicate tanpa `.git`.

### 2) Prompt template v3 khusus Codex
File: `docs/codex_exec_prompt_v3.txt`
- Menjadi source of truth prompt untuk run v3.
- Placeholder kontrak tetap sama agar artefak output tidak berubah.

### 3) Dokumentasi default digeser ke Codex v3
- `README.md` diarahkah ke `akuisisi_data_v3.sh`.
- `docs/SETUP.md` diubah ke langkah setup dan smoke test Codex.
- `docs/plan_v3.md` disesuaikan dengan flags + flow Codex.
- Ditambahkan `docs/TROUBLESHOOTING_CODEX_V3.md`.

### 4) Guardrail agent ditambahkan
File: `AGENTS.md`
- Kontrak CSV 2x12 + status enum ditulis eksplisit.
- Aturan anti-halusinasi angka dan kewajiban JSON fallback ditegaskan.

## Dampak

### Reliability
- Retry/checkpoint/validasi v3 tetap aktif.
- Runtime flags Codex bisa dikontrol eksplisit per run.

### Transparency
- Ringkasan run (`summary.md`) kini mencatat model + approval policy + sandbox mode.

### Scalability
- Siap untuk scale dari 8 URL ke 125+ URL dengan jalur automation Codex yang konsisten.

## Catatan Legacy
- Script/dokumen v1-v2 dan artefak `.claude/` dipertahankan untuk audit/historical reference.
