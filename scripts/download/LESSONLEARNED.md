# LESSON LEARNED & README — Data Acquisition Pipeline

## Context
Target kita: menata ulang downloader supaya:
- dijalankan lewat **bash orchestrator**,
- pakai env **`mamba run -n market_update`**,
- output align ke struktur repo saat ini (`data/YYYY-MM/{company}/...`),
- filename PDF unik per perusahaan dengan period (`{company_id}_{yyyy}_{mm}.pdf`),
- OCR support untuk Maipark,
- summary sukses/gagal jelas,
- single combined script untuk full workflow (download + pdftotext).

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

### 3) Output path & filename standardization (REVISED)
Di worker Python, output diarahkan ke:
- `data/YYYY-MM/{company_snake_case}/`

Nama PDF target (v2 - dengan period):
- `{company_snake_case}_{YYYY}_{MM}.pdf`

Contoh:
- `data/2026-04/pt_orion_reasuransi_indonesia/pt_orion_reasuransi_indonesia_2026_04.pdf`

**Update:** Format ini lebih informatif dan memudahkan tracking per-period tanpa perlu parsing folder.

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

### 6) PDF to Text conversion dengan OCR (Maipark)
Ditambahkan:
- `scripts/download/reasuransi_pdftotext_v1.sh`

Fitur:
- Scan PDF files dengan pattern `*_YYYY_MM.pdf`
- Untuk **Maipark**: OCR dulu → pdftotext
  - Command: `ocrmypdf --deskew --clean --oversample 400 --tesseract-pagesegmode 1`
  - Output intermediate: `{company}_YYYY_MM_ocr.pdf` (SAVED for audit)
  - Fallback otomatis ke pdftotext original jika OCR gagal
- Untuk non-Maipark: langsung pdftotext
- Support resume mode (`--resume`) untuk skip existing TXT
- Summary output:
  - `data/YYYY-MM/pdftotext_log.txt`
  - `data/YYYY-MM/pdftotext_summary.csv`
  - `data/YYYY-MM/pdftotext_summary.md`

### 7) Combined orchestrator script
Ditambahkan:
- `scripts/download/akuisisi_data_reasuransi.sh`

Fitur unified:
- Single entry point untuk **full workflow**: download PDFs → convert to text with OCR
- Phase 1: Download semua perusahaan (reuse dari reasuransi_download_v3.sh logic)
- Phase 2: PDF-to-text conversion dengan OCR support (reuse dari pdftotext_v1.sh logic)
- Flags:
  - `--skip-download`: hanya jalankan Phase 2
  - `--skip-pdftotext`: hanya jalankan Phase 1
  - `--resume`: skip existing files di kedua phase
- Summary terpadu:
  - `data/YYYY-MM/akuisisi_log.txt`
  - `data/YYYY-MM/akuisisi_summary.md`

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

### Bug D — Tugu Re discovery gagal on broken links (404)
**Gejala:** Download phase berhenti total untuk Tugu saat encounter link 404 (e.g., `/id/produk-dan-layanan`).

**Root cause:** crawler mengikuti link ke halaman lain domain yang return 404, `fetch_html()` raise exception, tidak di-handle graceful.

**Fix:** di `pt_tugu_reasuransi_indonesia_download.py`:
- Tambah explicit check untuk `requests.exceptions.HTTPError`
- Skip graceful untuk status 404, 410 (not found, gone)
- Continue crawling link lain instead of fail total
- Fallback ke browser rendering jika perlu

**Validation:**
- 2026-01: sebelum = FAIL (404 error), setelah = SUCCESS (404 skipped, continue crawl)

---

### Bug E — OCR TMPDIR environment issue di shell script
**Gejala:** ocrmypdf gagal dengan error `tesseract: failed to open file /tmp/ocrmypdf.io.XXX/000001_rasterize.png`.

**Root cause:** Shell function wrapper yang set `TMPDIR="$HOME/ocrmypdf_tmp"` tidak properly propagated dalam script context, atau directory tidak exist.

**Fix:** di `reasuransi_pdftotext_v1.sh`:
- Explicit `mkdir -p "$HOME/ocrmypdf_tmp"` sebelum ocrmypdf call
- Inline TMPDIR assignment: `TMPDIR="$HOME/ocrmypdf_tmp" ocrmypdf ...`
- Convert file path ke absolute: `$(cd "$(dirname "$pdf_path")" && pwd)/$(basename "$pdf_path")`

**Validation:**
- 2026-01 maipark: OCR sukses, `pt_reasuransi_maipark_indonesia_2026_01_ocr.pdf` tercipta (1.0M)
- pdftotext dari OCR'd PDF menghasilkan TXT readable (25K)

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
   - **Update:** Filename dengan period (`YYYY_MM`) lebih informatif daripada suffix generic (`_pdf`).

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

7. **Graceful error handling untuk crawler: skip broken links, don't fail**
   Saat crawler mengikuti link dan menemukan 404/410, should continue crawl untuk link lain, bukan fail total.
   - **Apply to Tugu:** explicit exception handling untuk HTTP errors dengan distinction antara recoverable (404, 410) vs fatal.

8. **Environment variable propagation di shell scripts perlu explicit setup**
   Shell function wrapper bisa tidak work konsisten. Better to:
   - Explicit `mkdir -p` untuk temp directories
   - Inline `TMPDIR=...` pada saat command execution
   - Convert paths ke absolute untuk cross-directory safety

9. **OCR output files worth keeping untuk audit trail**
   Don't delete intermediate OCR PDFs; keep them for verification & re-run if needed.
   - **Pattern:** `{company}_YYYY_MM_ocr.pdf` as audit artifact

10. **Combined orchestration script mengurangi operational complexity**
    Daripada user harus chain 2-3 scripts secara manual, single entry point (`akuisisi_data_reasuransi.sh`) dengan phase control:
    - `--skip-download`, `--skip-pdftotext` untuk flexible re-run
    - Unified logging & summary
    - Consistent resume behavior across phases

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

4. Monitor OCR success rate per period:
   - Track OCR success vs fallback untuk Maipark
   - Alert jika fallback rate > threshold (indicate environment/dependency issue)

5. Implement data completeness check:
   - Setelah Phase 2 selesai, validate semua company punya TXT output
   - Flag jika ada gap (company download OK tapi pdftotext failed)

---

# README — Cara Menjalankan Data Acquisition Pipeline

## Quick Start

```bash
# Full workflow untuk periode 2026-03
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03
```

Output akan berada di `data/2026-03/` dengan struktur:
```
data/2026-03/
├── akuisisi_log.txt              (log gabungan)
├── akuisisi_summary.md           (ringkasan)
├── pt_company_1_2026_03.pdf      (original PDF)
├── pt_company_1_2026_03_ocr.pdf  (maipark OCR'd PDF, jika applicable)
├── pt_company_1_2026_03.txt      (extracted text)
├── pt_company_2_2026_03.pdf
├── pt_company_2_2026_03.txt
└── ...
```

## Common Use Cases

### 1. Download + Convert (Full Run)
```bash
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03
```

### 2. Test Run (Dry Run)
```bash
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --dry-run
```
Shows what would be executed tanpa actual download/conversion.

### 3. Resume Incomplete Run
```bash
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --resume
```
Skip files yang sudah exist, hanya process yang belum.

### 4. Re-download Specific Period
```bash
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --force
```
Overwrite existing PDFs dan re-convert to text.

### 5. Only Download (Skip Text Conversion)
```bash
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --skip-pdftotext
```
Berguna jika hanya butuh PDF, atau ingin handle conversion terpisah.

### 6. Only Convert (Skip Download)
```bash
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --skip-download
```
Jika PDF sudah ada, hanya jalankan Phase 2 (PDF → TXT dengan OCR).

### 7. Advanced: Custom Timeout & Delay
```bash
./scripts/download/akuisisi_data_reasuransi.sh \
  --yyyy 2026 --mm 03 \
  --timeout 60 \
  --delay 3
```
Increase timeout per company & delay between companies.

### 8. Skip Problematic Company
```bash
./scripts/download/akuisisi_data_reasuransi.sh \
  --yyyy 2026 --mm 03 \
  --skip-nusantara
```
Skip PT Reasuransi Nusantara Makmur jika mengalami issue.

## Flags Reference

| Flag | Purpose |
|------|---------|
| `--yyyy YYYY` | 4-digit year (required) |
| `--mm MM` | 2-digit month 01-12 (required) |
| `--output-root DIR` | Output directory (default: `data`) |
| `--timeout SEC` | Download timeout per company in seconds (default: 30) |
| `--delay SEC` | Delay between companies in seconds (default: 2) |
| `--resume` | Skip existing files in both phases |
| `--force` | Overwrite existing PDFs & re-convert |
| `--dry-run` | Test run without actual execution |
| `--discover-only` | Discover reports tanpa download |
| `--use-browser` | Use Playwright for JS-rendered pages |
| `--debug-html` | Save HTML debug files on discovery failure |
| `--skip-nusantara` | Skip PT Reasuransi Nusantara Makmur |
| `--skip-download` | Skip Phase 1, only do pdftotext |
| `--skip-pdftotext` | Skip Phase 2, only download |
| `--help` | Show usage help |

## Output Files

### Phase 1 (Download) - Original Files
- `data/YYYY-MM/pt_company_name/pt_company_name_YYYY_MM.pdf` — Downloaded PDF

### Phase 2 (PDF→Text Conversion) - Generated Files
- `data/YYYY-MM/pt_company_name/pt_company_name_YYYY_MM.txt` — Extracted text (all companies)
- `data/YYYY-MM/pt_company_name/pt_company_name_YYYY_MM_ocr.pdf` — OCR'd PDF (Maipark only)

### Summary & Logs
- `data/YYYY-MM/akuisisi_log.txt` — Complete execution log
- `data/YYYY-MM/akuisisi_summary.md` — Human-readable summary

## Troubleshooting

### "mamba command not found"
```bash
# Ensure mamba is in PATH or activate conda environment
conda activate  # or source your setup
./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03
```

### "pdftotext command not found"
```bash
# Install poppler-utils
brew install poppler  # macOS
# or
apt-get install poppler-utils  # Linux
```

### "ocrmypdf command not found"
```bash
# Install ocrmypdf
pip install ocrmypdf
# Also ensure tesseract is installed:
brew install tesseract  # macOS
# or
apt-get install tesseract-ocr  # Linux
```

### OCR Fails for Maipark
- Script automatically fallback ke pdftotext original PDF
- Check log at `data/YYYY-MM/akuisisi_log.txt` for OCR error details
- If fallback successful, TXT will still be generated

### Download Fails for Specific Company
- Check log at `data/YYYY-MM/akuisisi_log.txt`
- Retry with `--skip-nusantara` if Nusantara is problematic
- Re-run with `--force` to retry all companies

## Performance Notes

- Typical full run (8 companies, download + OCR + conversion): **~2-3 minutes**
- Download phase only: **~30-60 seconds** (depends on website responsiveness)
- Conversion phase only (no OCR): **~10-20 seconds**
- Conversion with Maipark OCR: **+30-40 seconds** for OCR step

## Next Steps

- Check generated TXT files: `data/YYYY-MM/*/pt_*.txt`
- Review summary: `cat data/YYYY-MM/akuisisi_summary.md`
- Inspect logs if any failures: `tail -50 data/YYYY-MM/akuisisi_log.txt`

