# LESSON LEARNED & README — Data Acquisition Pipeline (Integrated)

## Context

Proyek ini memiliki pipeline **end-to-end**: download laporan PDF → convert PDF to text (with OCR) → extract key metrics.

Awalnya script tersebar di dua folder (`download/` dan `extract/`). Sekarang terintegrasi di `scripts/akuisisi_data/reasuransi/{company_name}/` supaya mirror struktur data output (`data/yyyy-mm/reasuransi/{company_name}/`).

Pola target nanti: single entry point orchestrator → Phase 1 (download) → Phase 2 (pdftotext with OCR) → Phase 3 (extract key metrics).

---

## What We Learned

### Download Pipeline

#### 1. Hard naming convention essensial
Orchestrator memvalidasi filename tertentu → semua worker harus strict patuh ke kontrak yang sama.
- Filename dengan period (`YYYY_MM`) lebih informatif daripada suffix generic (`_pdf`).
- Update struktur: `{company_snake_case}_YYYY_MM.pdf`

#### 2. Aggregator summary bisa salah jika output contract tidak seragam
Exit code 0 belum cukup; path/filename output juga harus konsisten.

#### 3. Web discovery logic harus domain-specific
Satu pendekatan crawler umum tidak cukup untuk semua situs; beberapa situs butuh endpoint AJAX khusus.

#### 4. Loose text context menyebabkan period mis-selection
Mengambil parent text bisa menambah noise (bulan tetangga) dan menyebabkan off-by-one month bug.

#### 5. Operational robustness matters
`mamba` lock/cache issue bisa merusak run walau logic benar; isolasi cache (`XDG_CACHE_HOME`) mengurangi flakiness.

#### 6. Graceful error handling untuk crawler
Saat crawler mengikuti link dan menemukan 404/410, harus continue crawl untuk link lain, bukan fail total.

#### 7. Environment variable propagation di shell scripts perlu explicit setup
Shell function wrapper bisa tidak work konsisten. Better to:
- Explicit `mkdir -p` untuk temp directories
- Inline `TMPDIR=...` pada saat command execution
- Convert paths ke absolute untuk cross-directory safety

#### 8. OCR output files worth keeping untuk audit trail
Don't delete intermediate OCR PDFs; keep them for verification & re-run if needed.
- **Pattern:** `{company}_YYYY_MM_ocr.pdf` as audit artifact

#### 9. Combined orchestration script mengurangi operational complexity
Daripada user harus chain 2-3 scripts secara manual, single entry point dengan phase control.

---

### Metrics Extraction

#### 1. Dynamic Path Resolution ✅
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # 5 parents from akuisisi_data/reasuransi/{company}/
```
- Script works from anywhere, no hardcoded paths
- Auto-discovers project structure based on file location

#### 2. Two-Stage Output Architecture ✅
```
Input TXT → Extract → Company CSV + Period Database CSV
```
- Per-company CSV: retains full data locally for reference
- Period database CSV: centralized aggregation for all companies
- Clear separation of concerns

#### 3. Append Mode for Aggregation ✅
```python
file_exists = DATABASE_CSV.exists()
mode = "a" if file_exists else "w"
```
- Multiple companies write to same period database without overwriting
- Enables batch processing or sequential runs

#### 4. Hard-Coded Company Metadata — FRAGILE ⚠️
```python
company = "PT Maskapai Reasuransi Indonesia Tbk."
jenis = "Reasuransi"
```
- Company name, insurance type baked into script
- Must modify 2 lines per new company
- **Risk:** Can't scale to 7+ companies without duplication

#### 5. Keywords Are Brittle ⚠️
```python
aset_2026, aset_prev = extract_two_numbers(text, "34 Jumlah Aset (20 + 33)")
```
- Exact text match required
- Each company's laporan keuangan may have different line numbers/labels
- **Risk:** Keywords must be verified per company; silent failures (None values) if text doesn't match

#### 6. Hard-Coded Extraction Calls — NOT DRY ⚠️
- 9 separate extraction lines; hard to maintain
- If a company has different metrics or ordering, need refactor

**Solution for scaling (future):** Template class with company-specific keyword overrides:
```python
class ResuransiExtractor:
    def get_keywords(self):
        """Override per company"""
        raise NotImplementedError

class MareInExtractor(ResuransiExtractor):
    def get_keywords(self):
        return {'aset': '34 Jumlah Aset (20 + 33)', ...}

class OrionExtractor(ResuransiExtractor):
    def get_keywords(self):
        return {'aset': 'X Jumlah Aset...', ...}
```

---

## Major Bugs Found & Fixed

### Bug A — False FAIL walau file sudah terdownload
**Gejala:** batch summary menandai FAIL padahal script company berhasil download.
**Root cause:** 3 script masih menulis nama file lama, sementara bash validator mencari pattern baru.
**Fix:** ubah output path di 3 scripts ke `{company}_pdf.pdf`.

### Bug B — Tugu Re selalu ambil bulan sebelumnya
**Gejala:** input Feb → yang terdownload Jan.
**Root cause:** candidate context di Tugu memasukkan parent/container text, yang sering memuat beberapa bulan.
**Fix:** stop pakai parent text, matching periode hanya dari anchor-level text + URL.

### Bug C — Nusantara data tidak ketemu di static page
**Gejala:** `not_found` walau data seharusnya tersedia.
**Root cause:** Daftar laporan dimuat via AJAX (`detailreport.php`), tidak selalu tersedia sebagai link statis.
**Fix:** tambah fetch AJAX `detailreport.php` by year, parse candidate dari response.

### Bug D — Tugu Re discovery gagal on broken links (404)
**Gejala:** Download phase berhenti total saat encounter link 404.
**Root cause:** crawler mengikuti link ke halaman lain domain yang return 404, `fetch_html()` raise exception.
**Fix:** explicit check untuk HTTP errors, skip graceful untuk 404/410, continue crawl.

### Bug E — OCR TMPDIR environment issue di shell script
**Gejala:** ocrmypdf gagal dengan error tessercact file not found.
**Root cause:** Shell function wrapper TMPDIR tidak properly propagated.
**Fix:** explicit `mkdir -p` sebelum ocrmypdf call, inline TMPDIR assignment, convert paths ke absolute.

---

## Validation & Testing

### Static validation
- `bash -n scripts/akuisisi_data/akuisisi_data_reasuransi.sh`
- `python3 -m py_compile` untuk semua worker scripts

### Real execution validation
- Run dengan browser mode + force untuk periode tahu pasti available
- Validasi path output sesuai struktur baru

---

## README — Cara Menjalankan

### Quick Start

```bash
# Full workflow untuk periode 2026-03
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03
```

Output akan berada di `data/2026-03/` dengan struktur:
```
data/2026-03/
├── akuisisi_log.txt              (log gabungan, period-level)
├── akuisisi_summary.md           (ringkasan, period-level)
├── database_reasuransi_2026_03.csv  (aggregate DB, period-level)
├── reasuransi/                   (industry subfolder)
│   ├── pt_company_1/
│   │   ├── pt_company_1_2026_03.pdf      (original PDF)
│   │   ├── pt_company_1_2026_03_ocr.pdf  (maipark OCR'd PDF, jika applicable)
│   │   └── pt_company_1_2026_03.txt      (extracted text)
│   ├── pt_company_1_2026_03_key_metric_2026_03.csv  (extracted metrics for aggregation)
│   └── ...
```

### Common Use Cases

#### 1. Download + Convert (Full Run)
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03
```

#### 2. Test Run (Dry Run)
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --dry-run
```

#### 3. Resume Incomplete Run
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --resume
```

#### 4. Re-download Specific Period
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --force
```

#### 5. Only Download (Skip Text Conversion)
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --skip-pdftotext
```

#### 6. Only Convert (Skip Download)
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 --skip-download
```

#### 7. Advanced: Custom Timeout & Delay
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh \
  --yyyy 2026 --mm 03 \
  --timeout 60 \
  --delay 3
```

#### 8. Skip Problematic Company
```bash
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh \
  --yyyy 2026 --mm 03 \
  --skip-nusantara
```

### Flags Reference

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

### Output Files

#### Phase 1 (Download)
- `data/YYYY-MM/reasuransi/pt_company_name/pt_company_name_YYYY_MM.pdf` — Downloaded PDF

#### Phase 2 (PDF→Text Conversion)
- `data/YYYY-MM/reasuransi/pt_company_name/pt_company_name_YYYY_MM.txt` — Extracted text
- `data/YYYY-MM/reasuransi/pt_company_name/pt_company_name_YYYY_MM_ocr.pdf` — OCR'd PDF (Maipark only)

#### Phase 3 (Metrics Extraction) — Soon
- `data/YYYY-MM/reasuransi/pt_company_name/pt_company_name_key_metric_YYYY_MM.csv` — Extracted metrics

#### Summary & Logs
- `data/YYYY-MM/akuisisi_log.txt` — Complete execution log
- `data/YYYY-MM/akuisisi_summary.md` — Human-readable summary
- `data/YYYY-MM/database_reasuransi_YYYY_MM.csv` — Aggregated metrics database

### Troubleshooting

#### "mamba command not found"
```bash
conda activate  # or source your setup
./scripts/akuisisi_data/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03
```

#### "pdftotext command not found"
```bash
brew install poppler  # macOS
apt-get install poppler-utils  # Linux
```

#### "ocrmypdf command not found"
```bash
pip install ocrmypdf
brew install tesseract  # macOS
apt-get install tesseract-ocr  # Linux
```

#### OCR Fails for Maipark
- Script automatically fallback ke pdftotext original PDF
- Check log at `data/YYYY-MM/akuisisi_log.txt` for OCR error details

#### Download Fails for Specific Company
- Check log at `data/YYYY-MM/akuisisi_log.txt`
- Retry with `--skip-nusantara` if Nusantara is problematic
- Re-run with `--force` to retry all companies

### Performance Notes

- Typical full run (8 companies, download + OCR + conversion): **~2-3 minutes**
- Download phase only: **~30-60 seconds**
- Conversion phase only (no OCR): **~10-20 seconds**
- Conversion with Maipark OCR: **+30-40 seconds**

---

## Recommended Next Steps

### Phase 1: Metrics Extraction Scaling
1. Identify keyword differences across 2-3 additional companies
2. Refactor to template class pattern (see pattern above)
3. Add company-specific subclasses for keyword overrides
4. Build unified orchestrator CLI for `--all` batch mode

### Phase 2: Output Validation
1. Post-download: validate ukuran minimum + PDF signature `%PDF-`
2. Post-conversion: validate semua company punya TXT output
3. Post-extraction: validate data completeness (no null metrics)

### Phase 3: Regression Testing
1. Fixture HTML tests untuk:
   - Tugu month selection
   - Nusantara AJAX parsing
   - Status mapping consistency
2. Data integrity checks per period

---

## File Structure (Current)

```
scripts/
├── akuisisi_data/
│   ├── LESSONLEARNED.md              (this file)
│   ├── akuisisi_data_reasuransi.sh   (orchestrator)
│   ├── download_reasuransi.py        (Python meta-orchestrator)
│   └── reasuransi/
│       ├── pt_indoperkasa_suksesjaya_reasuransi/
│       │   └── pt_indoperkasa_suksesjaya_reasuransi_download.py
│       ├── pt_maskapai_reasuransi_indonesia/
│       │   ├── pt_maskapai_reasuransi_indonesia_download.py
│       │   └── pt_maskapai_reasuransi_indonesia_key_metric.py
│       ├── pt_orion_reasuransi_indonesia/
│       │   └── pt_orion_reasuransi_indonesia_download.py
│       ├── pt_reasuransi_indonesia_utama/
│       │   └── pt_reasuransi_indonesia_utama_download.py
│       ├── pt_reasuransi_maipark_indonesia/
│       │   └── pt_reasuransi_maipark_indonesia_download.py
│       ├── pt_reasuransi_nasional_indonesia/
│       │   └── pt_reasuransi_nasional_indonesia_download.py
│       ├── pt_reasuransi_nusantara_makmur/
│       │   └── pt_reasuransi_nusantara_makmur_download.py
│       └── pt_tugu_reasuransi_indonesia/
│           └── pt_tugu_reasuransi_indonesia_download.py
├── utils/
│   ├── cleanup.sh
│   ├── setup.sh
│   └── validate_input.sh
└── workflow_with_ai/
    ├── akuisisi_data.sh
    ├── akuisisi_data_v2.sh
    └── akuisisi_data_v3.sh
```

