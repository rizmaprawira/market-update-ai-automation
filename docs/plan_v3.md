# PLAN v3 — Codex-Optimized Financial Report Processing Workflow

## Ringkasan
Workflow v3 mengunci kontrak output ke `data/YYYY-MM` dan menstandarkan alur per URL:
1) temukan & download PDF,
2) ekstrak konten PDF ke JSON hybrid lengkap,
3) ekstrak key metrics ke CSV 2 baris (current + prior),
4) append ke database CSV terpusat jika valid.

Fokus v3: reliability, transparency, dan kesiapan scale dari prototype 8 URL ke 125+ URL dengan runner `codex exec` non-interaktif.

## Kontrak I/O v3

### Input CLI
- `--YYYY <tahun>`: wajib, 4 digit
- `--MM <bulan>`: wajib, format `01..12`
- `--companies <file>`: wajib, 1 URL per baris, komentar `#` diizinkan
- `--model <nama_model>`: opsional, default `gpt-5.3-codex`
- `--approval-policy <mode>`: opsional, `untrusted|on-request|on-failure|never`, default `never`
- `--sandbox <mode>`: opsional, `read-only|workspace-write|danger-full-access`, default `workspace-write`
- `--delay <detik>`: opsional, default 5
- `--resume`: opsional
- `--fail-fast`: opsional

### Output period
`data/YYYY-MM/`
- `database_konsolidasi.csv`
- `log.txt`
- `.checkpoint_YYYY-MM.txt`
- `summary.md`
- `{company_snake_case}/...`

### Output per company
`data/YYYY-MM/{company_snake_case}/`
- `laporan_keuangan.pdf`
- `{company_snake_case}_raw.json`
- `{company_snake_case}_row.csv`
- `status.txt`

## Flow Eksekusi
1. Validasi argumen dan dependency (`codex`, template prompt, file URL).
2. Inisialisasi folder period + file konsolidasi + log.
3. Untuk tiap URL aktif:
   - Resolve `company_snake_case`.
   - Render prompt dari `docs/codex_exec_prompt_v3.txt`.
   - Jalankan `codex exec` dengan retry (maks 2 retry per URL).
   - Evaluasi `status.txt`.
   - Untuk status `BERHASIL/PARSIAL`: validasi CSV 2x12 + periode current/prior.
   - Append ke `database_konsolidasi.csv` bila valid.
   - Tulis checkpoint untuk `BERHASIL`, `PARSIAL`, `TIDAK_DITEMUKAN`.
4. Tulis `summary.md` dan statistik akhir run.

## Aturan Status
- `BERHASIL`: ekstraksi lengkap, CSV valid, tidak ada N/A.
- `PARSIAL`: data tersedia tapi ada field `N/A`.
- `TIDAK_DITEMUKAN`: laporan periode target tidak dipublikasikan.
- `GAGAL`: error teknis permanen setelah retry / output invalid.

Catatan:
- Jika status `BERHASIL` tetapi CSV berisi `N/A`, script mengoreksi otomatis ke `PARSIAL`.
- `TIDAK_DITEMUKAN` masuk checkpoint (tidak diulang saat resume).
- `GAGAL` tidak masuk checkpoint (diulang saat resume).

## Prompt Injection
Source of truth: `docs/codex_exec_prompt_v3.txt`.

Placeholder yang diisi script:
- `{WEBSITE_URL}`
- `{TAHUN}` / `{BULAN}`
- `{PERIODE}` / `{PERIODE_PRIOR}`
- `{OUTPUT_DIR}`
- `{COMPANY_DIR}`
- `{COMPANY_SNAKE_CASE}`
- `{JSON_OUTPUT_FILE}`
- `{CSV_OUTPUT_FILE}`
- `{STATUS_FILE}`

## Testing Strategy

### 1) Static checks
```bash
bash -n scripts/akuisisi_data_v3.sh
```

### 2) Smoke test (1 URL)
```bash
cat > /tmp/one_url.txt <<'TXT'
https://www.tugure.id/id/financial/monthly?page=1
TXT

./scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies /tmp/one_url.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 0
```

### 3) Prototype test (8 URL)
```bash
./scripts/akuisisi_data_v3.sh \
  --YYYY 2026 \
  --MM 04 \
  --companies config/link_reasuransi.txt \
  --model gpt-5.3-codex \
  --approval-policy never \
  --sandbox workspace-write \
  --delay 5
```

### 4) Resume test
```bash
./scripts/akuisisi_data_v3.sh --YYYY 2026 --MM 04 --companies config/link_reasuransi.txt --resume
```

## Troubleshooting Ringkas

### 1) `codex` tidak ditemukan
- Cek: `which codex`
- Solusi: install/authenticate Codex CLI, lalu ulangi run.

### 2) Template prompt tidak ditemukan
- Pastikan file `docs/codex_exec_prompt_v3.txt` ada.

### 3) CSV per-company invalid
- Cek `status.txt`, `*_row.csv`, dan `data/YYYY-MM/log.txt`.
- Pastikan output tepat 2 baris dan 12 kolom pipe-delimited.

### 4) Resume tidak skip URL
- Cek `.checkpoint_YYYY-MM.txt`.
- URL harus match persis dengan input URL.

### 5) Website sering timeout
- Gunakan `--delay` lebih tinggi dan jalankan `--resume`.
