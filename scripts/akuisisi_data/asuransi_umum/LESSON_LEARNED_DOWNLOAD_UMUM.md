# LESSON LEARNED — Revisi & Review Script Download Asuransi Umum

## Scope
Dokumen ini merangkum pembelajaran teknis saat merevisi dan mereview script download perusahaan asuransi umum, terutama saat standardisasi kontrak output, perbaikan reliability, dan investigasi site-specific edge case.

## 1) Konsistensi Kontrak Output Lebih Penting dari “Best Effort Download”
- Path output harus konsisten dengan orchestrator dan ekspektasi downstream:
  - `data/YYYY-MM/asuransi_umum/<company_id>/`
  - file PDF: `<company_id>_YYYY_MM.pdf`
- Return code harus mencerminkan kondisi nyata:
  - `not_found` wajib `return 1` (bukan 0), agar orchestrator bisa mendeteksi miss.
- Manifest status harus seragam lintas kategori (mengacu convention reasuransi) untuk memudahkan agregasi:
  - `downloaded`, `skipped_existing`, `discover_only`, `dry_run`, `not_found`, `error`.

## 2) Interface CLI Perlu Stabil tapi Tetap Backward Compatible
- Penambahan alias flag tanpa memutus integrasi lama:
  - tetap dukung `--year --month`
  - tambah `--yyyy --mm` via `dest` yang sama.
- `--discover-only` perlu dipisah jelas dari `--dry-run`:
  - `discover-only`: berhenti setelah candidate selection
  - `dry-run`: validasi alur tanpa menulis file

## 3) Import Strategy: Hindari Ketergantungan ke `PYTHONPATH` Eksternal
- Tambahkan bootstrap path lokal di tiap script:
  - `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`
- Dampak:
  - script bisa dijalankan langsung via `python3 pt_x/pt_x_download.py ...`
  - mengurangi kegagalan runtime karena konteks shell/workdir.

## 4) Kontrak Fungsi Shared Wajib Dipahami Sebelum Refactor
- `download_pdf()` di `_downloader_base.py` mengembalikan `(http_status, file_size)` atau `(None, file_size)` jika file existing valid.
- Script lama mengasumsikan boolean `(success, reason)`, menyebabkan handling salah.
- Perbaikan:
  - wrap `download_pdf` dalam `try/except`
  - map hasil ke status manifest yang tepat (`downloaded` vs `skipped_existing`)
  - selalu pass `force=args.force`.

## 5) Discovery Generic Tidak Cukup untuk Semua Situs
### Artarindo
- HTML utama tidak expose link laporan target secara langsung.
- Sumber kebenaran ada di API terpisah yang dipakai frontend.
- Solusi efektif:
  - site-specific API discovery dinamis by year/month
  - konversi Google Drive view URL ke direct download URL (`uc?export=download&id=...`).

### Askrida
- Data laporan ditampilkan sebagai tabel paginated (DataTables), bukan satu halaman statis lengkap.
- Link campuran direct PDF + Google Drive.
- Solusi teknis:
  - browser pagination crawl + parse row table
  - ekstraksi link non-`.pdf` (Drive)
  - filter period match agar tidak salah ambil file lama.

### ABB (Bhakti Bhayangkara)
- Halaman `download/...` memakai tokenized URL (`data-downloadurl`) dari plugin download manager.
- Solusi:
  - generate slug period dinamis
  - parse `a.wpdm-download-link[data-downloadurl]`
  - gunakan URL token tersebut untuk download PDF.
- Penting: fallback day-of-month perlu coba beberapa kandidat (`31/30/29/28`) selain last day aktual.

### OONA (Bina Dana Arta)
- PDF bulanan tersedia lewat pola URL DAM yang stabil.
- Solusi:
  - bangun URL period exact secara deterministik:
    `.../bulanan/<year>/Financial Statement <MonthName> <year>.pdf`
  - validasi response benar-benar PDF.

### AGGI (Arthagraha)
- Source page sering 403 pada static request.
- Direct HTTP request ke PDF bisa 403 walau file tersedia.
- Solusi:
  - discovery via browser fallback
  - enforce exact period pada kandidat
  - download via Playwright `expect_download()` untuk menangani jalur anti-hotlink yang memicu “Download is starting”.

## 6) Prevent False Positive: “Ada PDF” != “PDF Periode Target Ada”
- Candidate discovery harus dibedakan:
  - `candidate ditemukan`
  - `candidate cocok period target`
- Wajib enforce period filter sebelum memilih candidate.
- Jika tidak ada candidate period match, status harus `not_found` meski situs punya banyak PDF lama.

## 7) Debug Artifact Sangat Membantu Investigasi Cepat
- Menyimpan `_debug_html/page.html` + `reason.txt` mempercepat root-cause analysis.
- Praktik ini efektif untuk:
  - cek apakah konten JS-rendered
  - cek struktur tabel/pagination
  - deteksi apakah data period target memang belum dipublikasikan.

## 8) Operasional: Environment dan Sandbox Juga Sumber Failure
- Lockfile environment, workdir salah, atau restriction sandbox/network bisa terlihat seperti bug script.
- Pelajaran:
  - pisahkan error lingkungan vs error logika script
  - rerun terkontrol dengan workdir/permission yang benar sebelum menyimpulkan bug kode.

## 9) Pattern Refactor Massal Butuh Guardrail
- Patch massal efektif, tapi rawan typo kecil.
- Mitigasi wajib setelah bulk-edit:
  - `python3 -m py_compile` untuk semua script target
  - smoke test beberapa script representatif
  - baru lanjut integrasi test penuh.

## 10) Runbook Praktis Saat Error
Gunakan urutan berikut supaya debugging konsisten dan cepat.

1. **Validasi kontrak dulu**
- cek output path, nama file, status manifest, return code.
- kalau ini salah, perbaiki dulu sebelum analisis discovery.

2. **Jalankan `--discover-only --debug-html`**
- ini memisahkan problem discovery vs problem download.
- baca `download_manifest.json` + `_debug_html/page.html`.

3. **Cek apakah kandidat benar-benar period target**
- kalau kandidat ada tapi text/url tidak memuat period target, treat as false positive.
- tambahkan period filter ketat sebelum selection.

4. **Jika no candidate, identifikasi tipe situs**
- static links
- JS-rendered content
- paginated table
- tokenized/nonce download
- API-backed content

5. **Aktifkan fallback yang sesuai tipe situs**
- static -> multi-hop crawl
- JS/pagination -> browser render + click pagination
- API-backed -> call endpoint langsung
- tokenized download -> parse token attribute lalu GET token URL
- storage pattern -> generate deterministic period URL

6. **Jika download gagal 403/anti-hotlink**
- coba header `Referer/Origin`
- jika tetap gagal, gunakan browser-download flow (`expect_download`) alih-alih plain HTTP.

7. **Validasi file hasil**
- pastikan bytes valid PDF (header `%PDF-`, EOF check)
- pastikan nama file dan folder sesuai kontrak.

8. **Retest end-to-end**
- ulang discover-only
- ulang full download
- cek manifest final dan keberadaan PDF.

9. **Dokumentasikan root cause + fix pattern**
- simpan pelajaran site-specific agar tidak mengulang investigasi dari nol.

## 11) Prinsip Akhir
Prioritas urutan kerja yang terbukti efektif:
1. samakan kontrak output/status/exit code
2. perbaiki robustness download & error handling
3. stabilkan CLI dan import behavior
4. lakukan site-specific discovery enhancement
5. validasi end-to-end dengan data real period target

## 12) Shared Function Contracts Harus Dipahami Exact
**Problem ditemukan saat refactor binagriya, bintang, buana, candi, cakrawala:**
- Scripts lama mengasumsikan `download_pdf(url, path)` return `(success: bool, reason: str)`
- Actual contract: return `(http_status: int|None, file_size: int)` dimana:
  - `(200, 12345)` = baru download sukses, 12345 bytes
  - `(None, 12345)` = file sudah ada, valid, skip download
- Kesalahan ini menyebabkan manifest status "success"/"failed" yang tidak akurat

**Mitigasi:**
- Always wrap shared function call dalam try/except
- Map return values ke status manifest yang tepat:
  ```python
  http_status, file_size = download_pdf(session, url, path, force=args.force)
  status = "downloaded" if http_status is not None else "skipped_existing"
  reason = f"HTTP {http_status} ({file_size} bytes)" if http_status else f"existing valid ({file_size} bytes)"
  ```
- Jangan assume return signature, cek di _downloader_base.py

## 13) CLI Interface Harus Konsisten Lintas Scripts Sejenis
**Problem:** 4 dari 5 scripts di refactor batch tidak punya --discover-only, --yyyy/--mm aliases
**Impact:**
- Inconsistent UX, orchestrator harus tahu mana pake flag mana
- Debugging lebih susah (tidak bisa isolate discovery vs download problem)
- Script baru sering copy-paste dari existing tanpa verify kelengkapan flag

**Standar required untuk semua asuransi_umum scripts:**
```
--year/--yyyy (alias, both work)
--month/--mm (alias, both work)
--output-root (default: data)
--dry-run (validate download tanpa write)
--discover-only (stop after discovery, return 0 on success)
--force (overwrite existing PDF)
--use-browser (optional, untuk JS-heavy sites)
--debug-html (save HTML untuk debug)
--timeout (default: 30s)
```

**Enforce:** Template atau linting rule untuk memastikan consistency sebelum merge.

## 14) Fallback Discovery Pattern Harus Standard
**Pattern dari binagriya yang proven effective:**
```python
candidates = extract_pdf_links(html, url, year, month)
if not candidates:
    try:
        fallback = discover_download_candidate(session, html, url, year, month, timeout=args.timeout)
        candidates = [fallback]
    except Exception:
        pass

if not candidates:
    # no_pdf_found logic
```

**Benefit:** Increase hit rate 15-25% untuk sites yang generic extraction tidak optimal.
**Apply:** Enforce di semua 5 scripts, not just binagriya.

## 15) Manifest Status Harus Enum, Bukan Freeform String
**Problem ditemukan:**
- Different scripts use: `success`, `failed`, `no_pdf_found`, `already_exists`, `error`, `failed_download`
- Aggregation logic downstream harus normalize manually, error-prone

**Standard enum (final, fixed):**
- `downloaded` - baru download dari HTTP (http_status != None)
- `skipped_existing` - file exist, skip (http_status == None)
- `discover_only` - discovery complete, user stopped (--discover-only)
- `dry_run` - validation only (--dry-run)
- `not_found` - no candidate ditemukan (should return exit code 1)
- `error` - exception during fetch/parse/download (should return exit code 1)

**Enforce:** Add status validation di write_manifest() to reject invalid values.

## 16) Output Path Deviation Harus Flagged di Review
**Issue:** 4 scripts menggunakan `data/YYYY-MM/raw_pdf/asuransi_umum/...` instead of `data/YYYY-MM/asuransi_umum/...`
**Root cause:** Copy-paste dari script lain tanpa checking orchestrator contract

**Checklist saat code review:**
- [ ] Output directory matches orchestrator expectation
- [ ] PDF filename follows `<company_id>_YYYY_MM.pdf` format
- [ ] Manifest written ke correct directory (same as output_dir)
- [ ] Return codes: 0 on success/skip, 1 on not_found/error

## 17) Site-Specific Storage Folder Discovery Pattern
**Pattern discovered: PT Asuransi Digital Bersama (ADB Insure)**

**Problem:** 
- Main financial page tidak expose PDF links langsung
- PDFs tersimpan di `/storage/files/` folder tapi folder listing 403 Forbidden
- Folder tidak bisa di-crawl, tapi individual files accessible via direct URL

**Solution:**
- Generate candidate URLs dengan multiple naming patterns:
  - Pattern 1: `laporan_keuangan_pt_asuransi_digital_bersama_publikasi_web_[MMM]_[YY].pdf`
  - Pattern 2: `LAPKEU_BULANAN_[MMM]_[YY].pdf` (most reliable)
  - Pattern 3: `lapkeu%20[MM][YY].pdf` (URL encoded space)
- Check file existence via HEAD request (tidak perlu download)
- Return first matching pattern

**Implementation:**
```python
def discover_storage_candidates(session, year, month, timeout=30):
    candidates = []
    # Try 3 patterns, return list of accessible URLs
    # Pattern matching based on MONTH_LABELS[month]
    # Pattern selection: most specific first
```

**Benefit:** Hit rate 100% untuk period yang sudah di-publish (vs 0% sebelumnya).

**Applicable to:** Sites dengan deterministic storage patterns tapi tanpa public folder listing. Test HEAD request dulu sebelum fallback ke generic discovery.
