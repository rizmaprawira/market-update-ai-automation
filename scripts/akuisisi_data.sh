#!/bin/bash

# akuisisi_data.sh
# Usage: ./akuisisi_data.sh --2026 --04
# atau: ./akuisisi_data.sh --2025 --12

# Parse flags
TAHUN=""
BULAN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --20*|--19*)
            TAHUN="${1:2}"  # Remove '--' prefix
            shift
            ;;
        --0[1-9]|--1[0-2])
            BULAN="${1:2}"  # Remove '--' prefix
            shift
            ;;
        *)
            echo "❌ Unknown flag: $1"
            echo "Usage: ./akuisisi_data.sh --YYYY --MM"
            exit 1
            ;;
    esac
done

# Validate input
if [ -z "$TAHUN" ] || [ -z "$BULAN" ]; then
    echo "❌ Error: Tahun dan bulan harus diisi"
    echo "Usage: ./akuisisi_data.sh --2026 --04"
    exit 1
fi

TAHUN_BULAN="${TAHUN}-${BULAN}"

echo "============================================"
echo "🚀 AKUISISI DATA LAPORAN KEUANGAN"
echo "Periode: $TAHUN_BULAN"
echo "============================================"
echo ""

# Setup
CSV_OUTPUT="data_konsolidasi_${TAHUN_BULAN}.csv"
COMPANIES_FILE="perusahaan.txt"  # Simple text file dengan URLs
LOG_FILE="log_${TAHUN_BULAN}.txt"

# Initialize CSV dengan header
if [ ! -f "$CSV_OUTPUT" ]; then
    echo "tahun-bulan|jenis_asuransi|perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas" > "$CSV_OUTPUT"
    echo "✓ Created: $CSV_OUTPUT"
fi

# Count total companies
TOTAL=$(wc -l < "$COMPANIES_FILE")
CURRENT=0
BERHASIL=0
GAGAL=0

echo "📋 Total perusahaan: $TOTAL"
echo "📝 Log file: $LOG_FILE"
echo ""

# Loop semua URLs dari companies file
while IFS= read -r WEBSITE_URL; do
    # Skip empty lines dan comments
    [[ -z "$WEBSITE_URL" || "$WEBSITE_URL" == \#* ]] && continue
    
    CURRENT=$((CURRENT + 1))
    
    echo "[${CURRENT}/${TOTAL}] Processing: $WEBSITE_URL"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] START - $WEBSITE_URL" >> "$LOG_FILE"
    
    # PROMPT untuk Claude Code
    # Claude akan discover sendiri nama perusahaan dari website
    PROMPT="
    TASK: Akuisisi Laporan Keuangan Asuransi

    INSTRUKSI:
    1. Buka website ini: $WEBSITE_URL
    2. Cari dan download laporan keuangan untuk bulan: $BULAN tahun: $TAHUN (format: ${BULAN}/${TAHUN})
    3. Dari laporan PDF yang didownload:
       - Extract data finansial ke JSON
       - Identifikasi nama perusahaan dari laporan
       - Identifikasi jenis asuransi (asuransi umum/jiwa/reasuransi)
    4. Transform ke format CSV dengan kolom:
       tahun-bulan|jenis_asuransi|perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas
    5. Output file: output_${TAHUN_BULAN}.csv di current directory
    6. Format tahun-bulan: ${TAHUN}-${BULAN}

    CATATAN PENTING:
    - Semua output dalam BAHASA INDONESIA
    - Jika laporan tidak ada untuk periode ${BULAN}/${TAHUN}, output status TIDAK DITEMUKAN
    - Jika ekstraksi berhasil, simpan output_${TAHUN_BULAN}.csv dengan data 1 baris
    - Jika ekstraksi gagal, buat file error_${TAHUN_BULAN}.txt dengan penjelasan
    "
    
    # Send ke Claude Code
    echo "$PROMPT" | claude 2>&1 | tee -a "$LOG_FILE"
    
    # Check apakah output file berhasil dibuat
    if [ -f "output_${TAHUN_BULAN}.csv" ]; then
        # Append ke main CSV (skip header dari output)
        tail -n +2 "output_${TAHUN_BULAN}.csv" >> "$CSV_OUTPUT"
        echo "✓ BERHASIL: Data appended ke $CSV_OUTPUT"
        BERHASIL=$((BERHASIL + 1))
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS" >> "$LOG_FILE"
        
        # Cleanup temp file
        rm "output_${TAHUN_BULAN}.csv"
    else
        echo "✗ GAGAL: $WEBSITE_URL"
        GAGAL=$((GAGAL + 1))
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAILED" >> "$LOG_FILE"
    fi
    
    # Delay antara runs
    sleep 3
    
done < "$COMPANIES_FILE"

echo ""
echo "============================================"
echo "✅ SELESAI - Periode: $TAHUN_BULAN"
echo "============================================"
echo "📊 Hasil:"
echo "   Total diproses: $TOTAL"
echo "   Berhasil: $BERHASIL"
echo "   Gagal: $GAGAL"
echo ""
echo "📁 Output: $CSV_OUTPUT"
echo "📝 Log: $LOG_FILE"
echo "============================================"
