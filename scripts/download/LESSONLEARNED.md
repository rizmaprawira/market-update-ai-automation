# LESSON LEARNED — Downloader Review & Revise

## Context
Target kita: menata ulang downloader supaya:
- dijalankan lewat **bash orchestrator**,
- pakai env **`mamba run -n market_update`**,
- output align ke struktur repo saat ini (`data/YYYY-MM/{company}/...`),
- filename PDF unik per perusahaan,
- summary sukses/gagal jelas.

---

## What We Changed

### 1) Hard rename company downloader scripts
Semua script di `scripts/download` di-rename ke format lengkap PT:
- `pt_indoperkasa_suksesjaya_reasuransi_download.py`
- `pt_maskapai_reasuransi_indonesia_download.py`
- `pt_orion_reasuransi_indonesia_download.py`
- `pt_reasuransi_indonesia_utama_download.py`
- `pt_reasuransi_maipark_indonesia_download.py`
- `pt_reasuransi_nasional_indonesia_download.py`
- `pt_reasuransi_nusantara_makmur_download.py`
- `pt_tugu_reasuransi_indonesia_download.py`

### 2) Bash orchestrator baru
Ditambahkan:
- `scripts/download/reasuransi_download_v3.sh`

Fitur utama:
- period flags: `--YYYY`, `--MM`
- mode flags: `--resume`, `--fail-fast`, `--force`, `--dry-run`, `--discover-only`, `--use-browser`, `--debug-html`
- runtime flags: `--timeout`, `--delay`, `--output-root`
- mamba lock stabilization: `--mamba-cache-home` (default `/tmp/market-update-mamba-cache`)
- summary output:
  - `data/YYYY-MM/download_log.txt`
  - `data/YYYY-MM/download_summary.csv`
  - `data/YYYY-MM/download_summary.md`

### 3) Output path & filename standardization
Di worker Python, output diarahkan ke:
- `data/YYYY-MM/{company_snake_case}/`

Nama PDF target:
- `{company_snake_case}_pdf.pdf`

Contoh:
- `data/2026-04/pt_orion_reasuransi_indonesia/pt_orion_reasuransi_indonesia_pdf.pdf`

### 4) Status normalization
Kita standardkan status terminal agar orchestration konsisten:
- `downloaded`
- `skipped_existing`
- `discover_only`
- `dry_run`
- `not_found`
- `error`

### 5) Legacy compatibility touch
`download_reasuransi.py` disesuaikan agar tetap mengenali pola nama file baru `pt_*_download.py` bila dipakai sebagai fallback legacy runner.

---

## Major Bugs Found & Fixed

### Bug A — False FAIL walau file sudah terdownload
**Gejala:** batch summary menandai FAIL (`exit_zero_but_pdf_missing`) padahal script company berhasil download.

**Root cause:** 3 script masih menulis nama file lama (`{company}_{YYYY}_{MM}.pdf`), sementara bash validator mencari `{company}_pdf.pdf`.

**Fix:** ubah output path di:
- `pt_maskapai_reasuransi_indonesia_download.py`
- `pt_reasuransi_maipark_indonesia_download.py`
- `pt_reasuransi_nasional_indonesia_download.py`

ke `{company}_pdf.pdf`.

---

### Bug B — Tugu Re selalu ambil bulan sebelumnya
**Gejala:** input Feb -> yang terdownload Jan; input Apr -> yang terdownload Mar.

**Root cause:** candidate context di Tugu memasukkan parent/container text, yang sering memuat beberapa bulan sekaligus. Matching jadi longgar dan bisa salah pilih link.

**Fix (critical):** di `pt_tugu_reasuransi_indonesia_download.py`
- stop pakai parent text untuk candidate context,
- matching/scoring period hanya dari anchor-level text + URL candidate.

**Re-validation:**
- `2026-02` -> link terpilih `...2026-02...pdf` (benar)
- `2026-04` -> link terpilih `...2026-04...pdf` (benar)

---

### Bug C — Nusantara data tidak ketemu di static page
**Gejala:** `not_found` walau data seharusnya tersedia.

**Root cause:** daftar laporan Nusantara dimuat via AJAX (`detailreport.php`), tidak selalu tersedia sebagai link statis di HTML awal.

**Fix:** tambah fetch AJAX `detailreport.php` by year (dinamis dari flag), parse candidate dari response tersebut.

**Catatan:** sempat diminta skip Nusantara dulu (`--skip-nusantara`) untuk stabilisasi run 7 perusahaan lain. Flag ini ditambahkan di bash orchestrator.

---

## Validation We Ran

### Static validation
- `bash -n scripts/download/reasuransi_download_v3.sh`
- `python3 -m py_compile` untuk seluruh worker Python downloader

### Real execution validation (env market_update)
- Run `2026-02` dengan browser mode + force
- Hasil final (mode skip Nusantara): **7/7 SUCCESS**
- Tugu-specific rerun untuk `2026-02` dan `2026-04`: bulan target sekarang presisi sesuai input

---

## What We Learned

1. **Contract-first naming penting**
   Kalau orchestrator memvalidasi filename tertentu, semua worker harus strict patuh ke kontrak yang sama.

2. **Aggregator summary bisa salah jika output contract tidak seragam**
   Exit code 0 belum cukup; path/filename output juga harus konsisten.

3. **Web discovery logic harus domain-specific**
   Satu pendekatan crawler umum tidak cukup untuk semua situs; beberapa situs butuh endpoint AJAX khusus.

4. **Loose text context menyebabkan period mis-selection**
   Mengambil parent text bisa menambah noise (bulan tetangga) dan menyebabkan off-by-one month bug.

5. **Operational robustness matters**
   `mamba` lock/cache issue bisa merusak run walau logic benar; isolasi cache (`XDG_CACHE_HOME`) mengurangi flakiness.

6. **Replay against known published periods is essential**
   Uji terhadap periode yang pasti tersedia (mis. `2026-02`) sangat efektif untuk membedakan bug logic vs data availability.

---

## Recommended Next Hardening

1. Tambahkan assertion internal per worker:
   - kandidat terpilih harus mengandung bulan target secara eksplisit di anchor text/URL sebelum download.

2. Tambahkan post-download validation di orchestrator:
   - validasi ukuran minimum + signature PDF `%PDF-` untuk tiap file selesai download.

3. Tambahkan regression tests kecil (fixture HTML) untuk:
   - Tugu month selection,
   - Nusantara AJAX parsing,
   - status mapping consistency.

