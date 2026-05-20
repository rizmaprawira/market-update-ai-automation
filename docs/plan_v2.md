# Plan v2 — Automated Financial Report Processing

## Tujuan
Akuisisi data laporan keuangan dari 125+ perusahaan asuransi/reasuransi Indonesia untuk periode tertentu (YYYY-MM), ekstrak ke JSON, transform ke CSV, dan konsolidasikan ke satu file CSV terpusat siap untuk analisis & plotting.

---

## Workflow Architecture

### **1. Orkestrasi: `akuisisi_data_v2.sh`**
```bash
./akuisisi_data_v2.sh --2026 --04
./akuisisi_data_v2.sh --2025 --12 --resume --delay 10
```

**Flags yang tersedia:**

| Flag | Wajib | Default | Keterangan |
|------|-------|---------|------------|
| `--YYYY` | Ya | — | Tahun 4 digit |
| `--MM` | Ya | — | Bulan 2 digit (01–12) |
| `--resume` | Tidak | false | Skip URL yang sudah berhasil di-checkpoint |
| `--delay N` | Tidak | 5 | Jeda detik antara perusahaan |
| `--companies FILE` | Tidak | perusahaan.txt | Path file daftar URL |
| `--fail-fast` | Tidak | false | Hentikan script jika ada error (jangan lanjut ke URL berikutnya) |

---

### **2. Input: `perusahaan.txt`**
File teks sederhana, satu URL per baris. Baris dengan `#` di awal dan baris kosong diabaikan.

```
# Reasuransi
https://inare.co.id/en/report/
https://www.indonesiare.co.id/id/investor-relations/financial-report

# Asuransi Umum
https://www.orionre.id/id/publikasi.html
# ... dst
```

**Prototype:** `link_reasuransi.txt` (8 perusahaan)  
**Produksi:** `perusahaan.txt` (125+ perusahaan)

---

### **3. Execution Flow (Detail)**

```
User: ./akuisisi_data_v2.sh --2026 --04
    │
    ├─ Validasi flags (YYYY, MM format benar)
    ├─ Cek file perusahaan.txt ada
    ├─ Cek claude CLI tersedia di PATH
    │
    ├─ Buat direktori: output_2026-04/
    ├─ Init CSV dengan header (jika belum ada)
    ├─ Tulis header ke log_2026-04.txt
    │
    └─ FOR EACH URL di perusahaan.txt:
        │
        ├─ Skip jika baris kosong/komentar
        ├─ Skip jika mode --resume dan URL ada di checkpoint
        │
        ├─ Buat direktori: output_2026-04/001_inare.co.id/
        ├─ Hapus file temp lama (mencegah false-positive)
        │
        ├─ Generate prompt (URL + periode + direktori output)
        ├─ Jalankan: echo "$PROMPT" | claude --print --dangerouslySkipPermissions
        │
        │   Claude mengerjakan:
        │   ├─ Browse website & temukan laporan
        │   ├─ Download PDF → laporan_keuangan.pdf
        │   ├─ Extract data → data_ekstrak.json (WAJIB disimpan)
        │   ├─ Transform → data_output.csv (1 baris, 12 kolom, pipe-delimited)
        │   └─ Tulis status → status.txt (BERHASIL/PARSIAL/TIDAK_DITEMUKAN/GAGAL)
        │
        ├─ Validasi output:
        │   ├─ File CSV ada dan tidak kosong?
        │   ├─ Jumlah kolom = 12?
        │   └─ Field pertama = "2026-04"?
        │
        ├─ Append ke data_konsolidasi_2026-04.csv (jika valid)
        ├─ Catat di .checkpoint_2026-04.txt (jika berhasil)
        ├─ Log status ke log_2026-04.txt
        │
        └─ sleep 5s → proses URL berikutnya
    │
    └─ Cetak ringkasan: total/berhasil/gagal/dilewati
```

---

### **4. Struktur Direktori Output**

```
output_2026-04/
├─ data_konsolidasi_2026-04.csv    ← CSV terpusat (125+ baris)
├─ log_2026-04.txt                 ← Log lengkap semua proses
├─ .checkpoint_2026-04.txt         ← URL yang sudah berhasil (untuk --resume)
│
├─ 001_inare.co.id/
│   ├─ laporan_keuangan.pdf        ← PDF asli dari website
│   ├─ data_ekstrak.json           ← Data JSON (SELALU disimpan)
│   ├─ data_output.csv             ← 1 baris CSV hasil transform
│   └─ status.txt                  ← BERHASIL / PARSIAL / TIDAK_DITEMUKAN / GAGAL
│
├─ 002_marein-re.com/
│   └─ ...
│
└─ 003_orionre.id/
    └─ ...
```

---

### **5. Format Output**

**CSV konsolidasi (`data_konsolidasi_2026-04.csv`):**
```
tahun-bulan|jenis_asuransi|perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
2026-04|Reasuransi|INARE|Rp 5.2 triliun|Rp 1.8 triliun|N/A|Rp 120 miliar|Rp 115 miliar|Rp 45 miliar|Rp 12 miliar|312%|N/A
2026-04|Reasuransi|Indonesia Re|Rp 8.1 triliun|...
```

**JSON per-perusahaan (`data_ekstrak.json`):**
```json
{
  "perusahaan": "PT Reasuransi Nasional Indonesia (INARE)",
  "jenis_asuransi": "Reasuransi",
  "tahun_bulan": "2026-04",
  "aset": "Rp 5.217.432.000.000",
  "ekuitas": "Rp 1.834.211.000.000",
  "premi_penutupan_tidak_langsung": "N/A",
  "premi_bruto": "Rp 120.450.000.000",
  "pendapatan_premi": "Rp 115.200.000.000",
  "hasil_underwriting": "Rp 45.123.000.000",
  "laba_rugi_komprehensif": "Rp 12.345.000.000",
  "rasio_solvabilitas": "312%",
  "rasio_likuiditas": "N/A",
  "catatan": "PDF: laporan_keuangan_april2026.pdf. rasio_likuiditas tidak tersedia di laporan ini."
}
```

---

## Status Code Claude

| Status | Makna | Dikecualikan dari checkpoint? |
|--------|-------|-------------------------------|
| `BERHASIL` | Semua 12 field terisi dari data aktual | Tidak (di-skip saat resume) |
| `PARSIAL` | Data ada, beberapa field N/A | Tidak (di-skip saat resume) |
| `TIDAK_DITEMUKAN` | Laporan periode ini tidak ada | Ya (di-skip saat resume) |
| `GAGAL` | Error teknis | Ya (akan di-retry saat resume) |

---

## Cara Resume Setelah Error

Jika script berhenti di tengah (misal di perusahaan ke-50):
```bash
# Lanjutkan dari checkpoint — skip yang sudah berhasil
./akuisisi_data_v2.sh --2026 --04 --resume

# Checkpoint tersimpan di: output_2026-04/.checkpoint_2026-04.txt
# Format: SUCCESS:https://url.perusahaan.com
```

---

## Dependencies

| Tool | Wajib | Keterangan |
|------|-------|------------|
| `bash` | Ya | Versi 4+ (macOS bawaan cukup) |
| `claude` | Ya | Claude Code CLI, install dari https://claude.ai/code |
| `grep`, `sed`, `cut` | Ya | Standard Unix tools, sudah tersedia di macOS/Linux |
| `curl` atau `wget` | Ya | Untuk download PDF (Claude menggunakannya via Bash tool) |
| `jq` | Opsional | Untuk validasi/parsing JSON manual saat debugging |
| Internet | Ya | Untuk akses website dan download PDF |

---

---

## Contoh Penggunaan

```bash
# Prototype dengan 8 perusahaan
cp link_reasuransi.txt perusahaan.txt
./akuisisi_data_v2.sh --2026 --04

# Lanjutkan jika gagal di tengah
./akuisisi_data_v2.sh --2026 --04 --resume

# Produksi: tambah delay lebih panjang untuk 125+ perusahaan
./akuisisi_data_v2.sh --2026 --04 --delay 10 --companies perusahaan_lengkap.txt

# Test dengan fail-fast (debugging)
./akuisisi_data_v2.sh --2026 --04 --fail-fast

# Batch semua bulan dalam setahun
for bulan in {01..12}; do
    ./akuisisi_data_v2.sh --2025 --$(printf "%02d" $bulan)
    echo "Selesai bulan $bulan, jeda 60 detik..."
    sleep 60
done
```

---

## Testing Strategy

### Fase 1 — Tes Unit Manual (sebelum scale)
```bash
# Test 1: Flag parsing
./akuisisi_data_v2.sh --2026 --04          # Harus jalan normal
./akuisisi_data_v2.sh                       # Harus error: tahun bulan wajib
./akuisisi_data_v2.sh --2026               # Harus error: bulan wajib
./akuisisi_data_v2.sh --2026 --13          # Harus error: bulan tidak valid
./akuisisi_data_v2.sh --2026 --04 --delay abc  # Harus error: delay bukan angka

# Test 2: File tidak ada
./akuisisi_data_v2.sh --2026 --04 --companies tidak_ada.txt  # Harus error

# Test 3: Resume
./akuisisi_data_v2.sh --2026 --04          # Run pertama
./akuisisi_data_v2.sh --2026 --04 --resume  # Seharusnya skip semua yang berhasil
```

### Fase 2 — Tes dengan 1 Perusahaan
```bash
# Buat file test dengan 1 URL saja
echo "https://www.tugure.id/id/financial/monthly?page=1" > test_1.txt
./akuisisi_data_v2.sh --2026 --04 --companies test_1.txt

# Cek output:
ls output_2026-04/001_tugure.id/     # Harus ada pdf, json, csv, status.txt
cat output_2026-04/001_tugure.id/status.txt   # Harus: BERHASIL atau PARSIAL
cat output_2026-04/001_tugure.id/data_ekstrak.json | jq .   # Validasi JSON
cat output_2026-04/data_konsolidasi_2026-04.csv   # Harus ada 1 baris data
```

### Fase 3 — Tes Prototype (8 perusahaan)
```bash
./akuisisi_data_v2.sh --2026 --04 --companies link_reasuransi.txt

# Yang diverifikasi setelah selesai:
# 1. Jumlah baris CSV = jumlah perusahaan berhasil + 1 (header)
wc -l output_2026-04/data_konsolidasi_2026-04.csv

# 2. Semua kolom ada di setiap baris
awk -F'|' '{print NF}' output_2026-04/data_konsolidasi_2026-04.csv

# 3. Semua field pertama = periode yang benar
cut -d'|' -f1 output_2026-04/data_konsolidasi_2026-04.csv | sort | uniq

# 4. JSON tersimpan di semua direktori perusahaan
ls output_2026-04/*/data_ekstrak.json
```

### Fase 4 — Tes Produksi
- Scale ke 125 perusahaan dengan `--delay 10`
- Monitor log secara realtime: `tail -f output_2026-04/log_2026-04.txt`
- Setelah selesai, import CSV ke pandas/Excel untuk validasi akhir

---

## Troubleshooting

### Claude tidak mau jalan non-interaktif
```bash
# Cek versi claude
claude --version

# Tes manual non-interaktif
echo "Hitung 2+2" | claude --print

# Jika tidak ada flag --print, coba:
echo "Hitung 2+2" | claude
```

### Output CSV tidak terbuat
- Cek log: `cat output_YYYY-MM/log_YYYY-MM.txt`
- Cek direktori per-perusahaan: `ls output_YYYY-MM/NNN_domain/`
- Kemungkinan: Claude tidak punya izin nulis file → cek flag `--dangerouslySkipPermissions`
- Kemungkinan: Prompt tidak sampai ke Claude → cek pipe `echo "$PROMPT" | claude`

### PDF tidak bisa dibaca
- Cek apakah `pdftotext` tersedia: `which pdftotext`
- Install: `brew install poppler` (macOS) atau `apt install poppler-utils` (Linux)
- Beberapa PDF ter-enkripsi atau berbasis gambar — Claude mungkin perlu OCR

### Website tidak bisa diakses
- Cek koneksi internet
- Beberapa website memblokir akses dari bot/non-browser
- Pertimbangkan menambah `User-Agent` header di curl command di dalam prompt

### CSV ada kolom yang salah jumlah
- Buka file CSV per-perusahaan: `cat output_YYYY-MM/NNN_domain/data_output.csv`
- Kemungkinan: ada nilai yang mengandung pipe `|` → Claude perlu diinstruksikan escape karakter ini
- Tambahkan instruksi di prompt: "Jika nilai mengandung karakter pipe (|), ganti dengan spasi"

### Resume tidak bekerja
- Cek checkpoint file: `cat output_YYYY-MM/.checkpoint_YYYY-MM.txt`
- Format yang benar: `SUCCESS:https://url.com` (satu per baris, tanpa spasi)
- Pastikan URL di checkpoint cocok persis dengan URL di perusahaan.txt

---

## File Structure Lengkap

```
project/
├─ akuisisi_data_v2.sh          ← Script orkestrasi utama
├─ perusahaan.txt               ← Daftar URL produksi (125+)
├─ link_reasuransi.txt          ← Daftar URL prototype (8)
├─ claude_code_prompt.txt       ← Template prompt referensi
├─ plan_v2.md                   ← Dokumentasi ini
│
└─ output_2026-04/              ← Dibuat otomatis per periode
    ├─ data_konsolidasi_2026-04.csv
    ├─ log_2026-04.txt
    ├─ .checkpoint_2026-04.txt
    ├─ 001_inare.co.id/
    │   ├─ laporan_keuangan.pdf
    │   ├─ data_ekstrak.json
    │   ├─ data_output.csv
    │   └─ status.txt
    └─ ...
```
