# Review & Revision Summary

## Bug Kritis yang Ditemukan di v1

### 1. File output di-share antar perusahaan (BUG KRITIS)
**File:** `akuisisi_data.sh`, baris 103–111

Semua perusahaan menulis ke file yang sama: `output_${TAHUN_BULAN}.csv`.
Jika run sebelumnya gagal sebelum cleanup (`rm`), file sisa itu akan terdeteksi sebagai output
perusahaan berikutnya dan datanya salah-append ke CSV konsolidasi.

**Perbaikan di v2:** Setiap perusahaan punya direktori sendiri:
`output_2026-04/001_inare.co.id/data_output.csv`
File lama juga dihapus secara eksplisit sebelum Claude dijalankan.

---

### 2. Hitungan TOTAL perusahaan salah
**File:** `akuisisi_data.sh`, baris 56

```bash
TOTAL=$(wc -l < "$COMPANIES_FILE")
```
`wc -l` menghitung semua baris termasuk komentar (`#`) dan baris kosong.
Dengan 8 URL aktif dan 2 komentar, `TOTAL` bisa jadi 10 — progress bar menjadi misleading.

**Perbaikan di v2:**
```bash
TOTAL=$(grep -v "^[[:space:]]*$" "$COMPANIES_FILE" | grep -vc "^[[:space:]]*#" || true)
```

---

### 3. Tidak ada validasi file perusahaan.txt
**File:** `akuisisi_data.sh`, baris 46

Script langsung pakai `perusahaan.txt` tanpa cek apakah file ada. Jika file tidak ada,
`while read` hanya diam tanpa error yang jelas.

**Perbaikan di v2:** Ada pengecekan eksplisit:
```bash
if [[ ! -f "$COMPANIES_FILE" ]]; then
    echo "❌ Error: File perusahaan tidak ditemukan: $COMPANIES_FILE"
    exit 1
fi
```

---

### 4. `claude` dipanggil tanpa flag `--print` (non-interaktif)
**File:** `akuisisi_data.sh`, baris 100

```bash
echo "$PROMPT" | claude 2>&1 | tee -a "$LOG_FILE"
```
Tanpa flag `--print`, claude mungkin membuka sesi interaktif dan menunggu input terminal,
menyebabkan script hang selamanya saat dijalankan otomatis.

**Perbaikan di v2:** Gunakan `--print --dangerouslySkipPermissions` untuk mode automation penuh.

---

### 5. Prompt tidak instruksikan save JSON
**File:** `akuisisi_data.sh`, baris 77–97

Prompt ke Claude tidak ada instruksi untuk menyimpan JSON ke disk. Requirement "JSON harus disimpan"
tidak ter-cover.

**Perbaikan di v2:** Prompt secara eksplisit mewajibkan:
> "WAJIB simpan ke: {COMPANY_DIR}/data_ekstrak.json"
> "File JSON HARUS disimpan bahkan jika data tidak lengkap"

---

### 6. Tidak ada validasi CSV sebelum append
**File:** `akuisisi_data.sh`, baris 103–106

Jika file CSV output ada tapi berisi data yang salah format (jumlah kolom kurang, atau
field pertama bukan tahun-bulan yang tepat), data tersebut tetap di-append ke CSV konsolidasi.

**Perbaikan di v2:** Tiga lapisan validasi sebelum append:
1. File ada dan tidak kosong
2. Jumlah kolom = 12
3. Field pertama = `${TAHUN}-${BULAN}`

---

### 7. Tidak ada kemampuan resume
**File:** `akuisisi_data.sh`

Jika script berhenti di perusahaan ke-50 (jaringan putus, crash, dll), tidak ada cara
untuk melanjutkan dari titik itu. Harus mulai dari awal.

**Perbaikan di v2:** Flag `--resume` + checkpoint file `.checkpoint_YYYY-MM.txt`.
Setiap URL yang berhasil dicatat, dan saat resume URL itu di-skip.

---

## Improvement Tambahan

### Struktur direktori output
v1 membuang semua file di current directory.
v2 menggunakan `output_YYYY-MM/NNN_domain/` untuk setiap perusahaan — mudah di-debug
dan tidak mengotori root project.

### Validasi CLI dependency
v2 cek apakah `claude` tersedia di PATH sebelum mulai. Jika tidak ada, exit dengan pesan jelas.

### Nama direktori per-perusahaan
v2 menggunakan domain URL sebagai nama direktori (`001_inare.co.id`) — lebih mudah
diidentifikasi daripada hanya nomor urut.

### Flag `--delay` dan `--companies` configurable
v1 hard-code delay 3 detik dan nama file `perusahaan.txt`.
v2 keduanya bisa dikonfigurasi via flag.

### Status file eksplisit dari Claude
v2 mewajibkan Claude membuat `status.txt` dengan nilai yang terdefinisi
(BERHASIL / PARSIAL / TIDAK_DITEMUKAN / GAGAL), sehingga script bisa membedakan
"laporan memang tidak ada" vs "error teknis".

---

## File yang Dibuat/Diubah

| File | Status | Keterangan |
|------|--------|------------|
| `akuisisi_data.sh` | Tidak diubah | Original v1, tetap ada sebagai referensi |
| `akuisisi_data_v2.sh` | Dibuat baru | Versi improved — gunakan ini |
| `claude_code_prompt.txt` | Dibuat baru | Template prompt dengan dokumentasi teknis |
| `plan_v2.md` | Dibuat baru | Dokumentasi lengkap + testing + troubleshooting |
| `SUMMARY.md` | Dibuat baru | File ini |

---

## Perubahan Terakhir (v2.2)

- **Added `--permission-mode auto`** — Claude Code otomatis approve semua tool requests
  - Tidak perlu manual `y` confirmation setiap kali
  - Flags: `--print --model haiku --permission-mode auto`
  
- **Added `--model haiku`** — gunakan Haiku (fast & cost-efficient untuk batch)
  - Model ID: just `haiku` (bukan full version ID)
  
- **Added `--fail-fast` flag** — hentikan script jika ada error (tidak lanjut ke URL berikutnya)
  - Berguna untuk debugging & tes cepat
  - Default: false (lanjut ke perusahaan berikutnya meski ada error)

## Langkah Selanjutnya (Disarankan)

1. **Tes cepat dengan 1 URL dulu + fail-fast:**
   ```bash
   echo "https://www.tugure.id/id/financial/monthly?page=1" > test_1.txt
   ./akuisisi_data_v2.sh --2026 --04 --companies test_1.txt --fail-fast
   ```
   Claude akan meminta izin tool — jawab `y` untuk semua.

2. **Tes prototype 8 perusahaan:**
   ```bash
   ./akuisisi_data_v2.sh --2026 --04 --companies link_reasuransi.txt
   ```

3. **Validasi CSV output:**
   ```bash
   # Cek jumlah kolom setiap baris (semua harus 12)
   awk -F'|' '{print NR": "NF" kolom"}' output_2026-04/data_konsolidasi_2026-04.csv
   ```

4. **Scale ke produksi** setelah prototype berjalan bersih.
