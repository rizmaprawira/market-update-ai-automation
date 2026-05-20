# Troubleshooting Codex v3

## 1) `codex: command not found`

### Symptom
Script berhenti dengan error `perintah 'codex' tidak ditemukan di PATH`.

### Check
```bash
which codex
codex --version
```

### Fix
Install Codex CLI, login, lalu ulangi run.

## 2) Codex gagal start karena repo bukan git repo

### Symptom
`Not inside a trusted directory and --skip-git-repo-check was not specified.`

### Notes
Script v3 default sudah memanggil:
- `codex ... exec --skip-git-repo-check ...`

Jika Anda menjalankan command manual, tambahkan `--skip-git-repo-check`.

## 3) Prompt template tidak ditemukan

### Symptom
`template prompt tidak ditemukan: docs/codex_exec_prompt_v3.txt`

### Check
```bash
ls docs/codex_exec_prompt_v3.txt
```

### Fix
Pastikan file ada di path tersebut.

## 4) CSV per-company invalid

### Symptom
Log menunjukkan `CSV per-company tidak valid` dan status final `GAGAL`.

### Checks
1. File harus tepat 2 baris data (current + prior).
2. Tiap baris harus 12 kolom pipe-delimited.
3. Kolom pertama baris 1 = `YYYY-MM` current, baris 2 = prior year.

### Debug commands
```bash
cat data/2026-04/<company>/<company>_row.csv
awk -F'|' '{print NR, NF, $1}' data/2026-04/<company>/<company>_row.csv
cat data/2026-04/<company>/status.txt
```

## 5) Banyak timeout website

### Symptom
Banyak status `GAGAL` pada domain tertentu.

### Fix
- Naikkan `--delay` (misal 10-20 detik).
- Jalankan ulang dengan `--resume` agar yang sukses tidak diulang.

```bash
bash scripts/akuisisi_data_v3.sh --YYYY 2026 --MM 04 --companies config/link_reasuransi.txt --delay 15 --resume
```

## 6) Approval/sandbox tidak sesuai kebutuhan

### Symptom
Run terlalu restriktif atau terlalu permisif.

### Fix
Set explicit flag saat run:

```bash
bash scripts/akuisisi_data_v3.sh \
  --YYYY 2026 --MM 04 \
  --companies config/link_reasuransi.txt \
  --approval-policy on-request \
  --sandbox workspace-write
```

## 7) Resume tidak skip URL

### Symptom
URL yang sudah berhasil tetap diproses ulang.

### Checks
- Pastikan URL di input file sama persis dengan yang dicatat di checkpoint.
- Cek file checkpoint:

```bash
cat data/2026-04/.checkpoint_2026-04.txt
```

## 8) Ringkasan cepat investigasi

```bash
# cek error terbaru
rg -n "\[ERROR\]|\[WARN\]|GAGAL|PARSIAL" data/2026-04/log.txt -S | tail -50

# cek status seluruh company
find data/2026-04 -name status.txt -maxdepth 3 -print -exec cat {} \;
```
