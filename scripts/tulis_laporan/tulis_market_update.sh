#!/bin/bash

# tulis_market_update.sh — Automated Cohesive Market Update Report
#
# Generates a single comprehensive market update report covering all sectors
# (reasuransi, asuransi umum, asuransi jiwa) in one flowing document.
#
# Usage:
#   bash scripts/tulis_laporan/tulis_market_update.sh --yyyy 2026 --mm 04
#
# Output:
#   report/market_update_2026_04.md

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
YYYY=""
MM=""

# Parse flags
while [[ $# -gt 0 ]]; do
  case $1 in
    --yyyy)
      YYYY="$2"
      shift 2
      ;;
    --mm)
      MM="$2"
      shift 2
      ;;
    *)
      echo -e "${RED}❌ Unknown flag: $1${NC}"
      echo "Usage: bash scripts/tulis_laporan/tulis_market_update.sh --yyyy <YYYY> --mm <MM>"
      exit 1
      ;;
  esac
done

# Validate flags
if [[ -z "$YYYY" || -z "$MM" ]]; then
  echo -e "${RED}❌ Missing required flags${NC}"
  echo "Usage: bash scripts/tulis_laporan/tulis_market_update.sh --yyyy <YYYY> --mm <MM>"
  exit 1
fi

# Validate YYYY and MM format
if ! [[ "$YYYY" =~ ^[0-9]{4}$ ]]; then
  echo -e "${RED}❌ Invalid year format: $YYYY (must be 4 digits, e.g., 2026)${NC}"
  exit 1
fi

if ! [[ "$MM" =~ ^[0-9]{2}$ ]] || (( MM < 1 || MM > 12 )); then
  echo -e "${RED}❌ Invalid month format: $MM (must be 01-12)${NC}"
  exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Define paths
PERIOD_DIR="${PROJECT_ROOT}/data/${YYYY}-${MM}"
PROMPT_TEMPLATE="${SCRIPT_DIR}/prompt_tulis_market_update.md"
KNOWLEDGE_DIR="${PROJECT_ROOT}/knowledge"
REPORT_DIR="${PROJECT_ROOT}/report"

# Database files
DB_REASURANSI="${PERIOD_DIR}/database_reasuransi_${YYYY}_${MM}.csv"
DB_ASURANSI_UMUM="${PERIOD_DIR}/database_asuransi_umum_${YYYY}_${MM}.csv"
DB_ASURANSI_JIWA="${PERIOD_DIR}/database_asuransi_jiwa_${YYYY}_${MM}.csv"

# Knowledge files
KNOWLEDGE_REASURANSI="${KNOWLEDGE_DIR}/reinsurance-knowledge-id.md"
KNOWLEDGE_UMUM="${KNOWLEDGE_DIR}/general-insurance-knowledge-id.md"
KNOWLEDGE_JIWA="${KNOWLEDGE_DIR}/life-insurance-knowledge-id.md"

# Output file
OUTPUT_FILE="${REPORT_DIR}/market_update_${YYYY}_${MM}.md"

# Temp prompt file
TMP_PROMPT="/tmp/market_update_prompt_${YYYY}${MM}.txt"

echo -e "${YELLOW}📋 Market Update Report Generator${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Period: ${YELLOW}${YYYY}-${MM}${NC}"
echo ""

# Validate required files exist
echo -e "${YELLOW}✓ Validating input files...${NC}"

if [[ ! -f "$PROMPT_TEMPLATE" ]]; then
  echo -e "${RED}❌ Prompt template not found: $PROMPT_TEMPLATE${NC}"
  exit 1
fi

if [[ ! -f "$KNOWLEDGE_REASURANSI" ]]; then
  echo -e "${RED}❌ Knowledge file not found: $KNOWLEDGE_REASURANSI${NC}"
  exit 1
fi

if [[ ! -f "$KNOWLEDGE_UMUM" ]]; then
  echo -e "${RED}❌ Knowledge file not found: $KNOWLEDGE_UMUM${NC}"
  exit 1
fi

if [[ ! -f "$KNOWLEDGE_JIWA" ]]; then
  echo -e "${RED}❌ Knowledge file not found: $KNOWLEDGE_JIWA${NC}"
  exit 1
fi

# Check database files and load available ones
echo -e "${YELLOW}✓ Checking available databases...${NC}"

AVAILABLE_DBS=""
if [[ -f "$DB_REASURANSI" ]]; then
  echo "  ✓ Reasuransi database found"
  AVAILABLE_DBS="${AVAILABLE_DBS}reasuransi "
else
  echo "  ⚠ Reasuransi database not found (will skip)"
fi

if [[ -f "$DB_ASURANSI_UMUM" ]]; then
  echo "  ✓ Asuransi Umum database found"
  AVAILABLE_DBS="${AVAILABLE_DBS}umum "
else
  echo "  ⚠ Asuransi Umum database not found (will skip)"
fi

if [[ -f "$DB_ASURANSI_JIWA" ]]; then
  echo "  ✓ Asuransi Jiwa database found"
  AVAILABLE_DBS="${AVAILABLE_DBS}jiwa"
else
  echo "  ⚠ Asuransi Jiwa database not found (will skip)"
fi

if [[ -z "$AVAILABLE_DBS" ]]; then
  echo -e "${RED}❌ No database files found for period ${YYYY}-${MM}${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Input files validated${NC}"
echo ""

# Compute periods using bash
# Month name mapping (Indonesian)
declare -A MONTH_NAMES=(
  ["01"]="Januari" ["02"]="Februari" ["03"]="Maret" ["04"]="April"
  ["05"]="Mei" ["06"]="Juni" ["07"]="Juli" ["08"]="Agustus"
  ["09"]="September" ["10"]="Oktober" ["11"]="November" ["12"]="Desember"
)

PERIODE_UTAMA="${MONTH_NAMES[$MM]} ${YYYY}"

# Compute previous month (force decimal to avoid octal interpretation)
PREV_MM=$((10#$MM - 1))
PREV_YYYY=$YYYY
if (( PREV_MM < 1 )); then
  PREV_MM=12
  PREV_YYYY=$((YYYY - 1))
fi
PREV_MM_PADDED=$(printf "%02d" "$PREV_MM")
PERIODE_BULAN_SEBELUMNYA="${MONTH_NAMES[$PREV_MM_PADDED]} ${PREV_YYYY}"

# Compute previous year
PREV_YYYY_FULL=$((YYYY - 1))
PERIODE_TAHUN_SEBELUMNYA="${MONTH_NAMES[$MM]} ${PREV_YYYY_FULL}"

echo -e "${YELLOW}✓ Computed periods:${NC}"
echo "  Periode utama: ${PERIODE_UTAMA}"
echo "  Bulan sebelumnya: ${PERIODE_BULAN_SEBELUMNYA}"
echo "  Tahun sebelumnya: ${PERIODE_TAHUN_SEBELUMNYA}"
echo ""

# Assemble the final prompt using Python
echo -e "${YELLOW}✓ Assembling prompt...${NC}"

python3 - "$PROMPT_TEMPLATE" "$DB_REASURANSI" "$DB_ASURANSI_UMUM" "$DB_ASURANSI_JIWA" "$KNOWLEDGE_REASURANSI" "$KNOWLEDGE_UMUM" "$KNOWLEDGE_JIWA" "$PERIODE_UTAMA" "$PERIODE_BULAN_SEBELUMNYA" "$PERIODE_TAHUN_SEBELUMNYA" "$TMP_PROMPT" << 'PYTHON_EOF'
import sys
import os

# Read input files
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    prompt_template = f.read()

# Get database paths and check if they exist
db_reasuransi_path = sys.argv[2]
db_asuransi_umum_path = sys.argv[3]
db_asuransi_jiwa_path = sys.argv[4]

db_reasuransi_exists = os.path.exists(db_reasuransi_path) and os.path.getsize(db_reasuransi_path) > 0
db_asuransi_umum_exists = os.path.exists(db_asuransi_umum_path) and os.path.getsize(db_asuransi_umum_path) > 0
db_asuransi_jiwa_exists = os.path.exists(db_asuransi_jiwa_path) and os.path.getsize(db_asuransi_jiwa_path) > 0

with open(sys.argv[5], 'r', encoding='utf-8') as f:
    knowledge_reasuransi = f.read()

with open(sys.argv[6], 'r', encoding='utf-8') as f:
    knowledge_umum = f.read()

with open(sys.argv[7], 'r', encoding='utf-8') as f:
    knowledge_jiwa = f.read()

# Build database path references (instead of embedding the full data)
db_input_parts = []
if db_reasuransi_exists:
    db_input_parts.append(f"- Reasuransi: {db_reasuransi_path}")
if db_asuransi_umum_exists:
    db_input_parts.append(f"- Asuransi Umum: {db_asuransi_umum_path}")
if db_asuransi_jiwa_exists:
    db_input_parts.append(f"- Asuransi Jiwa: {db_asuransi_jiwa_path}")

db_input = "Database file paths:\n" + "\n".join(db_input_parts) if db_input_parts else "[Tidak ada database tersedia]"

# Also prepare available databases text with just file paths
db_reasuransi = f"File path: {db_reasuransi_path}" if db_reasuransi_exists else "[Tidak tersedia]"
db_asuransi_umum = f"File path: {db_asuransi_umum_path}" if db_asuransi_umum_exists else "[Tidak tersedia]"
db_asuransi_jiwa = f"File path: {db_asuransi_jiwa_path}" if db_asuransi_jiwa_exists else "[Tidak tersedia]"

# Build replacement dictionary (with file paths instead of content)
available_sectors = []
if db_reasuransi_exists:
    available_sectors.append('Reasuransi')
if db_asuransi_umum_exists:
    available_sectors.append('Asuransi Umum')
if db_asuransi_jiwa_exists:
    available_sectors.append('Asuransi Jiwa')

jenis_industri_str = ', '.join(available_sectors) if available_sectors else 'Industri Perasuransian'

replacements = {
    '{{DATABASE_REASURANSI}}': db_reasuransi,
    '{{DATABASE_ASURANSI_UMUM}}': db_asuransi_umum,
    '{{DATABASE_ASURANSI_JIWA}}': db_asuransi_jiwa,
    '{{DATABASE_INPUT}}': db_input,
    '{{PERIODE_UTAMA}}': sys.argv[8],
    '{{PERIODE_BULAN_SEBELUMNYA}}': sys.argv[9],
    '{{PERIODE_TAHUN_SEBELUMNYA}}': sys.argv[10],
    '{{JENIS_INDUSTRI}}': jenis_industri_str,
    '{{MODE_ANALISIS}}': 'Full Industry Analysis (semua mode yang tersedia sesuai data)',
    '{{reinsurance-knowledge-id.md}}': knowledge_reasuransi,
    '{{general-insurance-knowledge-id.md}}': knowledge_umum,
    '{{life-insurance-knowledge-id.md}}': knowledge_jiwa,
}

# Substitute placeholders
final_prompt = prompt_template
for placeholder, value in replacements.items():
    final_prompt = final_prompt.replace(placeholder, value)

# Prepend system instruction to prevent questions
system_instruction = """🚀 INSTRUKSI SISTEM: LANGSUNG TULIS LAPORAN, JANGAN TANYA

Anda adalah analis riset industri perasuransian Indonesia profesional yang HARUS:
1. LANGSUNG MENULIS LAPORAN TANPA PERTANYAAN APAPUN
2. BACA file database CSV dari path yang diberikan di sini
3. Membuat asumsi yang wajar untuk hal-hal yang ambigu
4. HANYA output markdown report — tidak ada preamble, tidak ada klarifikasi, hanya hasil akhir

---

"""

final_prompt = system_instruction + final_prompt

# Append cohesion instruction and critical "no questions" directive
cohesion_instruction = """

---

## ⚠️ INSTRUKSI KRITIS — JANGAN BERTANYA, LANGSUNG TULIS LAPORAN

**PENTING: Anda HARUS LANGSUNG MENULIS LAPORAN TANPA MENGAJUKAN PERTANYAAN KLARIFIKASI APAPUN.**

Database file paths disediakan di atas (dalam {{DATABASE_INPUT}}, {{DATABASE_REASURANSI}}, {{DATABASE_ASURANSI_UMUM}}, {{DATABASE_ASURANSI_JIWA}}).
BACA file CSV dari path tersebut dan analisis datanya langsung.

Gunakan data dan asumsi berikut:

### Asumsi yang SUDAH FINAL dan TIDAK PERLU DIKONFIRMASI:

1. **Periode perbandingan**:
   - Periode utama = bulan saat ini yang diberikan
   - Periode pembanding = bulan yang sama tahun lalu
   - JANGAN minta data bulan sebelumnya; gunakan perbandingan Year-on-Year (YoY) saja

2. **Jangkauan perusahaan**:
   - Analisis SEMUA perusahaan yang memiliki data dalam database yang tersedia
   - JANGAN membatasi hanya Top 10; analisis semua yang ada dalam database
   - Jika data untuk suatu sektor tidak tersedia, cukup abaikan sektor tersebut dari analisis

3. **Data kosong / N/A**:
   - Jika suatu metrik tidak tersedia untuk perusahaan tertentu, CUKUP CATAT sebagai "N/A" dalam narasi
   - JANGAN mengecualikan perusahaan dari analisis hanya karena ada nilai N/A
   - JANGAN mengisi data dengan asumsi atau hallucinate nilai

4. **Indonesia Re (Mode B)**:
   - Fokus pada benchmarking Indonesia Re vs total industri reasuransi
   - Jangan sebut nama perusahaan lain selain Indonesia Re

5. **Database yang tidak lengkap**:
   - Jika beberapa database sektor tidak tersedia, TETAP TULIS LAPORAN dengan sektor yang data-nya tersedia
   - Jangan mengabaikan sektor yang tersedia hanya karena sektor lain kosong
   - JANGAN ada catatan "data tidak lengkap" - tulis saja dengan data yang ada

### Output Format (HANYA markdown report):

Tulis HANYA dokumen laporan Market Update dalam format markdown.
- JANGAN ada preamble atau pengantar pertanyaan
- JANGAN ada klarifikasi
- JANGAN ada "Sebelum saya mulai..."
- JANGAN ada "Saya perlu bertanya..."
- OUTPUT = HANYA markdown report yang sudah jadi dan siap publikasi

---

## STRUKTUR LAPORAN

Gunakan Mode A, B, C, dan D secara BERURUTAN dalam SATU laporan yang mengalir dengan baik:

1. **Ringkasan Umum** — keadaan industri perasuransian Indonesia secara keseluruhan (reasuransi, asuransi umum, asuransi jiwa)
2. **Industri Reasuransi** — Mode A: Full Industry Analysis
3. **Posisi Indonesia Re** — Mode B: Indonesia Re vs Total Industri
4. **Industri Asuransi Umum** — Mode C: Full Industry Analysis
5. **Industri Asuransi Jiwa** — Mode D: Full Industry Analysis
6. **Kesimpulan Komprehensif** — ringkasan kondisi keseluruhan dan tren lintas sektor

Pastikan narasi dalam setiap bagian saling terhubung dengan transisi yang smooth antar sektor.
"""

final_prompt += cohesion_instruction

# Write to output file
with open(sys.argv[11], 'w', encoding='utf-8') as f:
    f.write(final_prompt)

print(f"✓ Prompt assembled and written to {sys.argv[11]}")
PYTHON_EOF

if [[ ! -f "$TMP_PROMPT" ]]; then
  echo -e "${RED}❌ Failed to assemble prompt${NC}"
  exit 1
fi

echo ""

# Create report directory if it doesn't exist
if [[ ! -d "$REPORT_DIR" ]]; then
  echo -e "${YELLOW}✓ Creating report directory: $REPORT_DIR${NC}"
  mkdir -p "$REPORT_DIR"
fi

# Check if Claude CLI is available
if ! command -v claude &>/dev/null; then
  echo -e "${RED}❌ Claude Code CLI not found in PATH${NC}"
  echo "Install from: https://claude.ai/code"
  exit 1
fi

echo -e "${YELLOW}✓ Claude CLI found${NC}"
echo ""

# Generate report using Claude CLI
echo -e "${YELLOW}📝 Generating market update report...${NC}"
echo "(This may take a minute or two)"
echo ""

if cat "$TMP_PROMPT" | claude --print --model claude-haiku-4-5-20251001 2>&1 | tee "$OUTPUT_FILE"; then
  echo ""
  echo -e "${GREEN}✅ Market Update Report Generated Successfully!${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "Output saved to: ${GREEN}$OUTPUT_FILE${NC}"
  echo ""

  # Cleanup temp file
  rm -f "$TMP_PROMPT"

  # Show file info
  if [[ -f "$OUTPUT_FILE" ]]; then
    FILE_SIZE=$(wc -c < "$OUTPUT_FILE")
    LINE_COUNT=$(wc -l < "$OUTPUT_FILE")
    echo -e "File size: ${YELLOW}$(numfmt --to=iec-i --suffix=B $FILE_SIZE 2>/dev/null || echo "${FILE_SIZE} bytes")${NC}"
    echo -e "Lines: ${YELLOW}${LINE_COUNT}${NC}"
  fi
else
  echo ""
  echo -e "${RED}❌ Error: Claude CLI execution failed${NC}"
  echo "Check the output above for details."

  # Cleanup temp file even on failure
  rm -f "$TMP_PROMPT"
  exit 1
fi
