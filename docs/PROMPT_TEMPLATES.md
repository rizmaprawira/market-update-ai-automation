# Template Prompt — Akuisisi Laporan Keuangan

Template referensi untuk prompt Claude Code. Versi aktual di-inject oleh `akuisisi_data_v2.sh` dengan variabel yang sudah disubstitusi.

## Variabel yang di-replace

- `{WEBSITE_URL}` → URL halaman laporan keuangan perusahaan
- `{BULAN}` → Bulan 2 digit (contoh: 04)
- `{TAHUN}` → Tahun 4 digit (contoh: 2026)
- `{TAHUN_BULAN}` → Format gabungan (contoh: 2026-04)
- `{COMPANY_DIR}` → Path direktori output per-perusahaan

---

## Task: Akuisisi Laporan Keuangan Bulanan - Dua Tahun

**WEBSITE URL:** `{WEBSITE_URL}`  
**PERIODE TARGET:** Bulan `{BULAN}`, Tahun `{TAHUN}`  
**DIREKTORI OUTPUT:** `{COMPANY_DIR}`

**PENTING:** Laporan keuangan menampilkan data KOMPARATIF (current year + prior year side-by-side).  
Ekstrak KEDUA periode dalam satu run: `{TAHUN}-{BULAN}` DAN `{TAHUN-1}-{BULAN}`

---

## Langkah Wajib (kerjakan berurutan)

### 1. TEMUKAN LAPORAN

- Buka website: `{WEBSITE_URL}`
- Navigasi ke halaman laporan keuangan/publikasi
- Cari laporan bulanan untuk bulan `{BULAN}` tahun `{TAHUN}`
- Jika ada beberapa format (PDF, Excel), prioritaskan PDF

### 2. DOWNLOAD PDF

- Download file laporan ke: `{COMPANY_DIR}/laporan_keuangan.pdf`
- Gunakan Bash dengan curl atau wget jika perlu
- Jika ada multiple file, pilih yang paling lengkap (laporan neraca/posisi keuangan)

### 3. EKSTRAK DATA KE JSON LENGKAP

**WAJIB — complete financial report extraction:**

- Baca seluruh konten PDF dan extract SEMUA data finansial
- Jangan cuma key metrics, ambil SEMUA: neraca detail, laba rugi detail, ratios, board, shareholders, dll
- Simpan ke: `{COMPANY_DIR}/data_ekstrak.json`

Format JSON HARUS mencakup:

```json
{
  "extraction_metadata": {
    "pdf_filename": "laporan_keuangan.pdf",
    "extracted_at": "ISO 8601 timestamp",
    "extraction_status": "complete|partial|failed"
  },
  "company_info": {
    "name": "nama lengkap perusahaan dari laporan",
    "jenis_asuransi": "Asuransi Umum | Asuransi Jiwa | Reasuransi",
    "reporting_period": "periode laporan (contoh: Per 30 April 2026 dan 2025)",
    "currency": "IDR (Juta Rupiah) atau lainnya",
    "report_date": "tanggal laporan dirilis"
  },
  "balance_sheet": {
    "assets": {
      "investments": { },
      "non_investments": { },
      "total_assets": { "2026": 775667, "2025": 567941 }
    },
    "liabilities_and_equity": {
      "liabilities": { },
      "equity": { }
    }
  },
  "income_statement": {
    "underwriting_results": { },
    "investment_results": { },
    "operating_expenses": { },
    "net_income": { }
  },
  "financial_ratios": {
    "solvency_ratios": { },
    "liquidity_ratios": { },
    "other_ratios": { }
  },
  "governance": {
    "board_of_directors": { },
    "shareholders": [ ]
  },
  "notes_and_observations": [
    "observasi penting dari laporan",
    "perubahan signifikan vs tahun lalu"
  ],
  "extraction_notes": {
    "sections_found": ["balance_sheet", "income_statement", "financial_ratios"],
    "sections_not_found": [],
    "parsing_issues": [],
    "missing_fields": {
      "premi_penutupan_tidak_langsung": "tidak ada di income statement"
    }
  }
}
```

**PENTING untuk `extraction_notes`:**
- List section mana saja yang DITEMUKAN (balance_sheet, income statement, dll)
- List section yang TIDAK DITEMUKAN
- Catat parsing issues atau PDF structure yang unusual
- Untuk field yang N/A di tahap selanjutnya, dokumentasi di `missing_fields`

### 4. EKSTRAK 12 KEY METRICS KE CSV

Simpan ke: `{COMPANY_DIR}/data_output.csv` **(DUA BARIS: current year + prior year)**

Extract dari JSON object yang sudah dibuat di Step 3, BUKAN dari PDF langsung.

#### Definisi 12 Metrik

| # | Metrik | Sumber | Catatan |
|---|--------|--------|---------|
| 1 | `aset` | `JSON.balance_sheet.assets.total_assets[2026]` | - |
| 2 | `ekuitas` | `JSON.balance_sheet.liabilities_and_equity.equity.total_equity[2026]` | - |
| 3 | `premi_penutupan_tidak_langsung` | `JSON.income_statement.underwriting_results` | Jika tidak ada → N/A |
| 4 | `premi_bruto` | `JSON.income_statement.underwriting_results` | - |
| 5 | `pendapatan_premi` | `JSON.income_statement.underwriting_results` (net/earned premium) | - |
| 6 | `hasil_underwriting` | `JSON.income_statement.underwriting_results` | - |
| 7 | `laba_rugi_komprehensif` | `JSON.income_statement.net_income` | Tandai NEGATIF jika rugi |
| 8 | `rasio_solvabilitas` | `JSON.financial_ratios.solvency_ratios` | - |
| 9 | `rasio_likuiditas` | `JSON.financial_ratios.liquidity_ratios` | - |

**Format CSV:**
- PURE ANGKA, delimiter PIPE (`|`), pemisah ribuan POINT (`.`)
- WAJIB hapus unit: "juta rupiah", "ribuan", "%" dll

**Contoh konversi:**
- `7,288,332 juta rupiah` → `7.288.332`
- `175%` → `175`
- `-29,397 juta rupiah` → `-29.397`

**STRUKTUR CSV (DUA BARIS):**

```
Baris 1: {TAHUN}-{BULAN}|jenis_asuransi|nama_perusahaan|aset_2026|ekuitas_2026|premi_penutupan_tl_2026|premi_bruto_2026|pendapatan_premi_2026|hasil_uw_2026|laba_rugi_komprehensif_2026|rasio_solv_2026|rasio_likuid_2026
Baris 2: {TAHUN-1}-{BULAN}|jenis_asuransi|nama_perusahaan|aset_2025|ekuitas_2025|premi_penutupan_tl_2025|premi_bruto_2025|pendapatan_premi_2025|hasil_uw_2025|laba_rugi_komprehensif_2025|rasio_solv_2025|rasio_likuid_2025
```

**UNTUK FIELD N/A:**
- Jika field TIDAK DITEMUKAN di JSON section → gunakan `N/A` di CSV
- DOKUMENTASI ALASAN di `extraction_notes` JSON (section `missing_fields`)
- STATUS: Jika ada N/A → **PARSIAL** (bukan BERHASIL)

### 5. BUAT STATUS FILE

Simpan ke: `{COMPANY_DIR}/status.txt`

Isi dengan SATU KATA saja (tanpa spasi, tanpa newline ekstra):

- **BERHASIL** → kedua baris (current + prior year) terisi LENGKAP tanpa N/A
- **PARSIAL** → data ada tapi ada field yang N/A
- **TIDAK_DITEMUKAN** → laporan periode `{BULAN}/{TAHUN}` tidak ada di website
- **GAGAL** → error teknis (download gagal, PDF rusak, parsing error, dll)

**PENTING: HITUNG JUMLAH N/A DI CSV**
- Jika 0 field N/A → **BERHASIL**
- Jika 1+ field N/A → **PARSIAL**

---

## Aturan Penting

- Semua output dalam BAHASA INDONESIA
- Salin nilai numerik persis dari laporan sesuai definisi metrik di atas
- EKSTRAK DARI KOLOM YANG TEPAT: bukan dari nilai random atau estimasi
- File JSON HARUS disimpan bahkan jika data tidak lengkap
- Jika website tidak bisa diakses: status GAGAL, JSON dengan catatan error
- Jika prior year tidak tersedia di laporan: baris 2 boleh semua N/A, status tetap PARSIAL bukan GAGAL

---

## Catatan Teknis untuk Pengembang

### Cara invokasi di script

```bash
echo "$PROMPT" | claude --print --model haiku
```

### File .claude/settings.json (WAJIB ada)

```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "WebFetch"]
  }
}
```

Ini pre-approve semua tool requests tanpa manual confirmation.

#### Alternatif lebih aman (granular permissions)

```json
{
  "permissions": {
    "allow": [
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Read(*)",
      "Write({COMPANY_DIR}/*)"
    ]
  }
}
```

### Tips Troubleshooting

- **Jika Claude tidak bisa browse:** pastikan WebFetch tool diizinkan
- **Jika PDF tidak bisa dibaca:** coba install pdftotext (poppler-utils)
- **Jika JSON tidak tersimpan:** cek izin write ke direktori output
- **Jika output kosong:** cek apakah `--print` flag berfungsi di versi Claude CLI
