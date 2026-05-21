#!/bin/bash

# ============================================================
# akuisisi_data_v2.sh
# Skrip orkestrasi otomatis akuisisi laporan keuangan asuransi
#
# Usage:
#   ./akuisisi_data_v2.sh --2026 --04
#   ./akuisisi_data_v2.sh --2025 --12 --resume
#   ./akuisisi_data_v2.sh --2026 --04 --delay 10 --companies perusahaan.txt
#   ./akuisisi_data_v2.sh --2026 --04 --fail-fast
#
# Flags:
#   --YYYY       Tahun (wajib, contoh: --2026)
#   --MM         Bulan dengan leading zero (wajib, contoh: --04)
#   --resume     Lanjutkan dari checkpoint; skip URL yang sudah berhasil
#   --delay N    Jeda dalam detik antar perusahaan (default: 5)
#   --companies  Path ke file daftar URL (default: perusahaan.txt)
#   --fail-fast  Hentikan script jika ada error (jangan lanjut ke URL berikutnya)
# ============================================================

set -u  # Hentikan jika ada variabel yang tidak didefinisikan

# ─────────────────────────────────────────────
# KONFIGURASI DEFAULT
# ─────────────────────────────────────────────
DELAY_DETIK=5
COMPANIES_FILE="perusahaan.txt"
MODE_RESUME=false
MODE_FAIL_FAST=false
JUMLAH_KOLOM_CSV=12   # Jumlah kolom yang diharapkan di output CSV

# ─────────────────────────────────────────────
# PARSE FLAGS
# ─────────────────────────────────────────────
TAHUN=""
BULAN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --20*|--19*)
            TAHUN="${1:2}"   # Hapus prefix '--'
            shift
            ;;
        --0[1-9]|--1[0-2])
            BULAN="${1:2}"   # Hapus prefix '--'
            shift
            ;;
        --resume)
            MODE_RESUME=true
            shift
            ;;
        --fail-fast)
            MODE_FAIL_FAST=true
            shift
            ;;
        --delay)
            if [[ -z "${2:-}" || ! "$2" =~ ^[0-9]+$ ]]; then
                echo "❌ --delay membutuhkan angka positif"
                exit 1
            fi
            DELAY_DETIK="$2"
            shift 2
            ;;
        --companies)
            if [[ -z "${2:-}" ]]; then
                echo "❌ --companies membutuhkan path file"
                exit 1
            fi
            COMPANIES_FILE="$2"
            shift 2
            ;;
        --help|-h)
            grep "^#" "$0" | head -20 | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "❌ Flag tidak dikenal: $1"
            echo "Usage: ./akuisisi_data_v2.sh --YYYY --MM [--resume] [--delay N] [--companies FILE]"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────
# VALIDASI INPUT
# ─────────────────────────────────────────────

# Tahun dan bulan wajib diisi
if [[ -z "$TAHUN" || -z "$BULAN" ]]; then
    echo "❌ Error: Tahun dan bulan wajib diisi"
    echo "Usage: ./akuisisi_data_v2.sh --2026 --04"
    exit 1
fi

# File daftar perusahaan harus ada
if [[ ! -f "$COMPANIES_FILE" ]]; then
    echo "❌ Error: File perusahaan tidak ditemukan: $COMPANIES_FILE"
    echo "Pastikan file ada atau gunakan --companies <path>"
    exit 1
fi

# Claude Code CLI harus tersedia
if ! command -v claude &>/dev/null; then
    echo "❌ Error: Claude Code CLI tidak ditemukan di PATH"
    echo "Install dari: https://claude.ai/code"
    exit 1
fi

TAHUN_BULAN="${TAHUN}-${BULAN}"
TAHUN_MINUS_1=$((TAHUN - 1))
TAHUN_BULAN_PRIOR="${TAHUN_MINUS_1}-${BULAN}"

# ─────────────────────────────────────────────
# SETUP DIREKTORI DAN FILE OUTPUT
# ─────────────────────────────────────────────
OUTPUT_DIR="output_${TAHUN_BULAN}"
CSV_OUTPUT="${OUTPUT_DIR}/data_konsolidasi_${TAHUN_BULAN}.csv"
LOG_FILE="${OUTPUT_DIR}/log_${TAHUN_BULAN}.txt"
CHECKPOINT_FILE="${OUTPUT_DIR}/.checkpoint_${TAHUN_BULAN}.txt"

mkdir -p "$OUTPUT_DIR"

# Header banner
echo "============================================"
echo "  AKUISISI DATA LAPORAN KEUANGAN"
echo "  Periode   : $TAHUN_BULAN"
echo "  Companies : $COMPANIES_FILE"
echo "  Output    : $OUTPUT_DIR/"
echo "  Resume    : $MODE_RESUME"
echo "  Fail-fast : $MODE_FAIL_FAST"
echo "  Delay     : ${DELAY_DETIK}s"
echo "============================================"
echo ""

# Inisialisasi CSV dengan header jika file belum ada
if [[ ! -f "$CSV_OUTPUT" ]]; then
    echo "tahun-bulan|jenis_asuransi|perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas" > "$CSV_OUTPUT"
    echo "✓ CSV output dibuat: $CSV_OUTPUT"
fi

# Tulis header log (append, bukan overwrite — agar log lama tetap ada)
{
    echo "============================================"
    echo "LOG AKUISISI - Periode: $TAHUN_BULAN"
    echo "Mulai    : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Resume   : $MODE_RESUME"
    echo "Companies: $COMPANIES_FILE"
    echo "============================================"
} >> "$LOG_FILE"

# Hitung total perusahaan aktif (exclude baris kosong dan komentar)
TOTAL=$(grep -v "^[[:space:]]*$" "$COMPANIES_FILE" | grep -vc "^[[:space:]]*#" || true)
# Jika grep tidak menemukan apapun (file kosong), set ke 0
[[ -z "$TOTAL" || "$TOTAL" == "0" ]] && { echo "❌ Tidak ada URL aktif di $COMPANIES_FILE"; exit 1; }

CURRENT=0
BERHASIL=0
GAGAL=0
DILEWATI=0

echo "📋 Total perusahaan aktif : $TOTAL"
echo "📝 Log file               : $LOG_FILE"
echo ""

# ─────────────────────────────────────────────
# MAIN LOOP — Proses setiap URL
# ─────────────────────────────────────────────
while IFS= read -r WEBSITE_URL; do

    # Skip baris kosong dan komentar
    [[ -z "$WEBSITE_URL" || "$WEBSITE_URL" =~ ^[[:space:]]*# ]] && continue

    CURRENT=$((CURRENT + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    WAKTU_MULAI=$(date +%s)

    # Buat nama direktori dari domain URL (untuk keterbacaan)
    SAFE_NAME=$(echo "$WEBSITE_URL" | sed 's|https\?://||' | cut -d'/' -f1 | sed 's/[^a-zA-Z0-9._-]/_/g')
    COMPANY_DIR="${OUTPUT_DIR}/$(printf "%03d" $CURRENT)_${SAFE_NAME}"
    mkdir -p "$COMPANY_DIR"

    # Path file output per-perusahaan
    TEMP_CSV="${COMPANY_DIR}/data_output.csv"
    TEMP_JSON="${COMPANY_DIR}/data_ekstrak.json"
    STATUS_FILE="${COMPANY_DIR}/status.txt"

    echo "─────────────────────────────────────────"
    echo "[${CURRENT}/${TOTAL}] $WEBSITE_URL"
    echo "[$TIMESTAMP] Direktori output: $COMPANY_DIR"
    echo "[$TIMESTAMP] START [$CURRENT/$TOTAL] $WEBSITE_URL" >> "$LOG_FILE"

    # Mode resume: skip URL yang sudah dicatat sebagai sukses
    if $MODE_RESUME && grep -q "^SUCCESS:${WEBSITE_URL}$" "$CHECKPOINT_FILE" 2>/dev/null; then
        echo "⏭️  Dilewati (sudah diproses, mode --resume aktif)"
        echo "[$TIMESTAMP] SKIPPED (resume) $WEBSITE_URL" >> "$LOG_FILE"
        DILEWATI=$((DILEWATI + 1))
        continue
    fi

    # Hapus file output lama dari run sebelumnya yang gagal
    # (Penting: mencegah false-positive dari file sisa sebelumnya)
    rm -f "$TEMP_CSV" "$TEMP_JSON" "$STATUS_FILE"

    # ─────────────────────────────────────────────
    # BANGUN PROMPT UNTUK CLAUDE CODE
    # ─────────────────────────────────────────────
    PROMPT="TASK: Akuisisi Laporan Keuangan Bulanan - Dua Tahun (Current + Prior Year)

WEBSITE URL: ${WEBSITE_URL}
PERIODE TARGET: Bulan ${BULAN}, Tahun ${TAHUN}
DIREKTORI OUTPUT: ${COMPANY_DIR}

PENTING: Laporan keuangan menampilkan data KOMPARATIF (current year + prior year side-by-side).
Ekstrak KEDUA periode dalam satu run: ${TAHUN}-${BULAN} DAN ${TAHUN_MINUS_1}-${BULAN}

LANGKAH WAJIB (kerjakan berurutan):

1. TEMUKAN LAPORAN
   - Buka website: ${WEBSITE_URL}
   - Navigasi ke halaman laporan keuangan/publikasi
   - Cari laporan bulanan untuk bulan ${BULAN} tahun ${TAHUN}
   - Jika ada beberapa format (PDF, Excel), prioritaskan PDF

2. DOWNLOAD PDF
   - Download file laporan ke: ${COMPANY_DIR}/laporan_keuangan.pdf
   - Gunakan Bash dengan curl atau wget jika perlu
   - Jika ada multiple file, pilih yang paling lengkap (laporan neraca/posisi keuangan)

3. EKSTRAK DATA KE JSON (WAJIB — selalu simpan JSON meski tidak lengkap)
   - Baca konten PDF dan identifikasi data finansial
   - Identifikasi: nama perusahaan dan jenis asuransi (Asuransi Umum / Asuransi Jiwa / Reasuransi)
   - Simpan ke: ${COMPANY_DIR}/data_ekstrak.json (untuk periode utama: ${TAHUN}-${BULAN})
   - Format JSON:
     {
       \"perusahaan\": \"nama lengkap dari laporan\",
       \"jenis_asuransi\": \"Asuransi Umum atau Asuransi Jiwa atau Reasuransi\",
       \"tahun_bulan\": \"${TAHUN}-${BULAN}\",
       \"aset\": \"nilai total aset (salin persis dari laporan termasuk satuan)\",
       \"ekuitas\": \"nilai total ekuitas\",
       \"premi_penutupan_tidak_langsung\": \"nilai atau N/A jika tidak ada\",
       \"premi_bruto\": \"nilai atau N/A\",
       \"pendapatan_premi\": \"nilai atau N/A\",
       \"hasil_underwriting\": \"nilai atau N/A\",
       \"laba_rugi_komprehensif\": \"nilai laba atau rugi (tandai negatif jika rugi)\",
       \"rasio_solvabilitas\": \"persentase atau N/A\",
       \"rasio_likuiditas\": \"persentase atau N/A\",
       \"catatan\": \"keterangan: nama file PDF, URL sumber, field yang tidak ditemukan\"
     }

4. BUAT CSV OUTPUT (DUA BARIS — current year + prior year, TANPA header)
   - Simpan ke: ${COMPANY_DIR}/data_output.csv

   DEFINISI METRIK (ekstrak dari PDF laporan keuangan):
   ─────────────────────────────────────────────────
   • aset: Dari Neraca/Balance Sheet, baris \"Total Aset\"
   • ekuitas: Dari Neraca/Balance Sheet, baris \"Total Ekuitas\" atau \"Total Shareholders' Equity\"
   • premi_penutupan_tidak_langsung: Dari Laporan Laba Rugi, baris \"Premi Penutupan tidak langsung\"
     (jika tidak ada, gunakan N/A — jangan samakan dengan premi bruto)
   • premi_bruto: Dari Laporan Laba Rugi, baris \"Premi Bruto\" atau total dari premi langsung + tidak langsung
   • pendapatan_premi: Dari Laporan Laba Rugi, baris \"Pendapatan Premi Netto\" atau \"Earned Premium\"
   • hasil_underwriting: Dari Laporan Laba Rugi, baris \"Hasil Underwriting\"
   • laba_rugi_komprehensif: Dari Laporan Laba Rugi, baris \"Laba Rugi Komprehensif\" (bottom line)
     Tandai NEGATIF jika rugi (contoh: -29.397)
   • rasio_solvabilitas: Dari catatan laporan atau tabel rasio, nilai persentase (tanpa % symbol)
   • rasio_likuiditas: Dari catatan laporan atau tabel rasio, nilai persentase (tanpa % symbol)
   ─────────────────────────────────────────────────

   Format: PURE ANGKA, delimiter PIPE (|), pemisah ribuan POINT (.)
   WAJIB hapus: \"juta rupiah\", \"ribuan\", \"%\" dan unit lainnya

   Contoh konversi:
   * \"7,288,332 juta rupiah\" → 7.288.332
   * \"175%\" → 175
   * \"-29,397 juta rupiah\" → -29.397
   * \"123,456 ribu rupiah\" → 123.456

   STRUKTUR CSV (dua baris):
   Baris 1: ${TAHUN}-${BULAN}|jenis_asuransi|nama_perusahaan|aset_current|ekuitas_current|premi_penutupan_tidak_langsung_current|premi_bruto_current|pendapatan_premi_current|hasil_underwriting_current|laba_rugi_komprehensif_current|rasio_solvabilitas_current|rasio_likuiditas_current
   Baris 2: ${TAHUN_MINUS_1}-${BULAN}|jenis_asuransi|nama_perusahaan|aset_prior|ekuitas_prior|premi_penutupan_tidak_langsung_prior|premi_bruto_prior|pendapatan_premi_prior|hasil_underwriting_prior|laba_rugi_komprehensif_prior|rasio_solvabilitas_prior|rasio_likuiditas_prior

   PENTING:
   - Tepat 12 kolom per baris, dipisah PIPE (|)
   - Field kosong/tidak ada: isi N/A (tanpa tanda petik)
   - Ekstrak kolom PRIOR YEAR (biasanya kolom sebelah kanan/kolom perbandingan di PDF)
   - JANGAN gunakan angka random — jika data prior year tidak ada, tulis N/A untuk semua field di baris 2

5. BUAT STATUS FILE
   - Simpan ke: ${COMPANY_DIR}/status.txt
   - Isi dengan SATU KATA saja (tanpa spasi, tanpa newline ekstra):
     BERHASIL          → kedua baris (current + prior year) memiliki semua 12 field terisi
     PARSIAL           → data ada tapi beberapa field tidak ditemukan (diisi N/A)
     TIDAK_DITEMUKAN   → laporan periode ${BULAN}/${TAHUN} tidak ada di website
     GAGAL             → error teknis (website down, PDF rusak, dll)

ATURAN PENTING:
- Semua output dalam BAHASA INDONESIA
- Salin nilai numerik persis dari laporan sesuai definisi metrik di atas
- EKSTRAK DARI KOLOM YANG TEPAT: bukan dari nilai random atau estimasi
- File JSON HARUS disimpan bahkan jika data tidak lengkap
- Jika website tidak bisa diakses: status GAGAL, JSON dengan catatan error
- Jika prior year tidak tersedia di laporan: baris 2 boleh semua N/A, status tetap PARSIAL bukan GAGAL"

    # ─────────────────────────────────────────────
    # JALANKAN CLAUDE CODE
    # ─────────────────────────────────────────────
    echo "   🤖 Menjalankan Claude Code (permission pre-approved via .claude/settings.json)..."
    if echo "$PROMPT" | claude --print --model haiku 2>&1 | tee -a "$LOG_FILE"; then
        CLAUDE_EXIT_CODE=0
    else
        CLAUDE_EXIT_CODE=$?
        echo "   ⚠️  Claude exit code: $CLAUDE_EXIT_CODE"
    fi

    # Hitung durasi
    WAKTU_SELESAI=$(date +%s)
    DURASI=$((WAKTU_SELESAI - WAKTU_MULAI))

    # ─────────────────────────────────────────────
    # VALIDASI OUTPUT DAN APPEND KE CSV KONSOLIDASI
    # ─────────────────────────────────────────────
    STATUS_VALUE=""
    [[ -f "$STATUS_FILE" ]] && STATUS_VALUE=$(tr -d '[:space:]' < "$STATUS_FILE")

    # Jika Claude exit dengan error dan --fail-fast aktif, hentikan sekarang
    if [[ $CLAUDE_EXIT_CODE -ne 0 && "$MODE_FAIL_FAST" == "true" ]]; then
        echo ""
        echo "❌ FAIL-FAST: Claude error di perusahaan $CURRENT/$TOTAL"
        echo "   Exit code: $CLAUDE_EXIT_CODE"
        echo "   Hentikan script (mode --fail-fast aktif)"
        echo ""
        echo "[$TIMESTAMP] FAIL_FAST_EXIT [exit:$CLAUDE_EXIT_CODE] $WEBSITE_URL" >> "$LOG_FILE"
        exit 1
    fi

    if [[ -f "$TEMP_CSV" && -s "$TEMP_CSV" ]]; then
        # Ambil semua baris valid (tidak header, tidak kosong) — diharapkan DUA baris
        DATA_ROWS=$(grep -v "^tahun-bulan\|^[[:space:]]*$" "$TEMP_CSV")
        ROW_COUNT=$(echo "$DATA_ROWS" | wc -l | tr -d ' ')

        if [[ -z "$DATA_ROWS" || "$ROW_COUNT" -eq 0 ]]; then
            echo "❌ GAGAL - CSV ada tapi tidak ada baris data valid"
            echo "[$TIMESTAMP] FAILED [empty_data] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
            GAGAL=$((GAGAL + 1))
        elif [[ "$ROW_COUNT" -ne 2 ]]; then
            echo "❌ GAGAL - Diharapkan 2 baris (current + prior year), tetapi ditemukan $ROW_COUNT"
            echo "[$TIMESTAMP] FAILED [wrong_row_count:$ROW_COUNT] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
            GAGAL=$((GAGAL + 1))
        else
            # Validasi setiap baris
            VALIDATION_OK=true
            ROW_NUM=0
            APPENDED_ROWS=0
            HAS_NA_VALUES=false
            NA_FIELDS=""

            while IFS= read -r DATA_BARIS; do
                ROW_NUM=$((ROW_NUM + 1))

                # Hitung jumlah kolom (jumlah pipe + 1)
                JUMLAH_PIPE=$(echo "$DATA_BARIS" | tr -cd '|' | wc -c | tr -d ' ')
                JUMLAH_KOLOM_ACTUAL=$((JUMLAH_PIPE + 1))

                if [[ "$JUMLAH_KOLOM_ACTUAL" -ne "$JUMLAH_KOLOM_CSV" ]]; then
                    echo "❌ GAGAL - Baris $ROW_NUM: Jumlah kolom salah: $JUMLAH_KOLOM_ACTUAL (diharapkan $JUMLAH_KOLOM_CSV)"
                    echo "   Baris: $DATA_BARIS"
                    echo "[$TIMESTAMP] FAILED [row_${ROW_NUM}_wrong_columns:$JUMLAH_KOLOM_ACTUAL] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
                    VALIDATION_OK=false
                    break
                fi

                # Validasi field pertama (tahun-bulan)
                FIELD_PERTAMA=$(echo "$DATA_BARIS" | cut -d'|' -f1)
                EXPECTED_PERIOD=""
                if [[ $ROW_NUM -eq 1 ]]; then
                    EXPECTED_PERIOD="${TAHUN}-${BULAN}"
                else
                    EXPECTED_PERIOD="${TAHUN_MINUS_1}-${BULAN}"
                fi

                if [[ "$FIELD_PERTAMA" != "$EXPECTED_PERIOD" ]]; then
                    echo "❌ GAGAL - Baris $ROW_NUM: Periode salah (diharapkan '$EXPECTED_PERIOD', dapat '$FIELD_PERTAMA')"
                    echo "[$TIMESTAMP] FAILED [row_${ROW_NUM}_wrong_period] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
                    VALIDATION_OK=false
                    break
                fi

                # Hitung N/A values di baris ini
                NA_COUNT=$(echo "$DATA_BARIS" | grep -o '|N/A' | wc -l | tr -d ' ')
                if [[ $NA_COUNT -gt 0 ]]; then
                    HAS_NA_VALUES=true
                    NA_FIELDS="${NA_FIELDS}Baris $ROW_NUM: $NA_COUNT field N/A; "
                fi

                # Validasi lulus untuk baris ini — append ke CSV konsolidasi
                echo "$DATA_BARIS" >> "$CSV_OUTPUT"
                APPENDED_ROWS=$((APPENDED_ROWS + 1))

            done <<< "$DATA_ROWS"

            # Jika semua baris valid dan terabsen append
            if [[ "$VALIDATION_OK" == "true" && "$APPENDED_ROWS" -eq 2 ]]; then
                # Validasi status consistency dengan N/A values
                if [[ "$HAS_NA_VALUES" == "true" && "$STATUS_VALUE" == "BERHASIL" ]]; then
                    echo "⚠️  WARNING - Status BERHASIL tapi ada N/A values: $NA_FIELDS"
                    echo "   Claude harus status PARSIAL jika ada N/A"
                    echo "[$TIMESTAMP] SUCCESS_WITH_WARNING [na_values:$NA_FIELDS] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
                    echo "✅ APPENDED - 2 baris (${TAHUN}-${BULAN} + ${TAHUN_MINUS_1}-${BULAN}), status: ${STATUS_VALUE} [WARNING: ada N/A]"
                elif [[ "$HAS_NA_VALUES" == "true" ]]; then
                    echo "✅ APPENDED - 2 baris (${TAHUN}-${BULAN} + ${TAHUN_MINUS_1}-${BULAN}), status: ${STATUS_VALUE} [N/A: $NA_FIELDS]"
                    echo "[$TIMESTAMP] SUCCESS [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
                else
                    echo "✅ BERHASIL - 2 baris (${TAHUN}-${BULAN} + ${TAHUN_MINUS_1}-${BULAN}) appended (${DURASI}s, status: ${STATUS_VALUE:-?})"
                    echo "[$TIMESTAMP] SUCCESS [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
                fi
                # Catat di checkpoint agar resume bisa skip ini
                echo "SUCCESS:${WEBSITE_URL}" >> "$CHECKPOINT_FILE"
                BERHASIL=$((BERHASIL + 1))
            else
                echo "❌ GAGAL - Validasi tidak lulus (appended: $APPENDED_ROWS/2)"
                echo "[$TIMESTAMP] FAILED [validation_failed] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
                GAGAL=$((GAGAL + 1))
            fi
        fi

    elif [[ "$STATUS_VALUE" == "TIDAK_DITEMUKAN" ]]; then
        echo "⚠️  TIDAK DITEMUKAN - Laporan ${TAHUN}-${BULAN} tidak ada di website (${DURASI}s)"
        echo "[$TIMESTAMP] NOT_FOUND [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
        # Catat di checkpoint (tidak perlu di-retry saat resume)
        echo "SUCCESS:${WEBSITE_URL}" >> "$CHECKPOINT_FILE"
        GAGAL=$((GAGAL + 1))

    else
        echo "❌ GAGAL - Output tidak ditemukan (status: '${STATUS_VALUE:-tidak ada}', ${DURASI}s)"
        echo "   Cek log: $LOG_FILE"
        echo "   Cek dir: $COMPANY_DIR"
        echo "[$TIMESTAMP] FAILED [no_output,status:${STATUS_VALUE:-none}] [${DURASI}s] $WEBSITE_URL" >> "$LOG_FILE"
        GAGAL=$((GAGAL + 1))
    fi

    # Konfirmasi JSON tersimpan
    if [[ -f "$TEMP_JSON" ]]; then
        echo "   📄 JSON tersimpan: $TEMP_JSON"
    else
        echo "   ⚠️  JSON tidak tersimpan di $TEMP_JSON"
    fi

    echo ""

    # Jeda antar perusahaan (tidak perlu jeda setelah yang terakhir)
    if [[ "$CURRENT" -lt "$TOTAL" ]]; then
        sleep "$DELAY_DETIK"
    fi

done < "$COMPANIES_FILE"

# ─────────────────────────────────────────────
# RINGKASAN AKHIR
# ─────────────────────────────────────────────
TIMESTAMP_SELESAI=$(date '+%Y-%m-%d %H:%M:%S')

echo ""
echo "============================================"
echo "  SELESAI — Periode: $TAHUN_BULAN"
echo "  Waktu selesai: $TIMESTAMP_SELESAI"
echo "============================================"
echo "  Hasil:"
echo "    Total diproses  : $((BERHASIL + GAGAL))"
echo "    ✅ Berhasil     : $BERHASIL"
echo "    ❌ Gagal        : $GAGAL"
echo "    ⏭️  Dilewati    : $DILEWATI"
echo ""
echo "  File output:"
echo "    CSV konsolidasi : $CSV_OUTPUT"
echo "    Log             : $LOG_FILE"
echo "    Per-perusahaan  : $OUTPUT_DIR/NNN_domain/"
echo "============================================"

# Tulis ringkasan ke log
{
    echo ""
    echo "============================================"
    echo "SELESAI: $TIMESTAMP_SELESAI"
    echo "Berhasil: $BERHASIL | Gagal: $GAGAL | Dilewati: $DILEWATI"
    echo "============================================"
} >> "$LOG_FILE"
