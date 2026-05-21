#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./asuransi_umum_download.sh --yyyy 2026 --mm 03 [options]

Download financial reports for Asuransi Umum (General Insurance) companies

Required:
  --yyyy <year>                  4-digit year (e.g. 2026)
  --mm <month>                   2-digit month (01..12)

Optional:
  --output-root <dir>            Output root (default: data)
  --timeout <sec>                Timeout per company downloader (default: 30)
  --delay <sec>                  Delay between companies (default: 1)
  --resume                       Skip existing PDFs
  --fail-fast                    Stop on first failure
  --force                        Overwrite existing PDFs
  --dry-run                      Test run without actual download
  --discover-only                Discover reports without downloading
  --use-browser                  Use browser rendering for discovery
  --debug-html                   Save HTML debug files
  --help                         Show this help
USAGE
}

log() {
  local level="$1"
  local msg="$2"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] [$level] $msg"
  if [[ -n "$LOG_FILE" ]]; then
    echo "[$ts] [$level] $msg" >> "$LOG_FILE"
  fi
}

# Parse arguments
TAHUN=""
BULAN=""
OUTPUT_ROOT="data"
TIMEOUT=30
DELAY_SEC=1
MODE_RESUME=false
MODE_FAIL_FAST=false
FLAG_FORCE=false
FLAG_DRY_RUN=false
FLAG_DISCOVER_ONLY=false
FLAG_USE_BROWSER=false
FLAG_DEBUG_HTML=false

LOG_FILE=""
FAIL_LOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yyyy)
      TAHUN="${2:-}"
      shift 2
      ;;
    --mm)
      BULAN="${2:-}"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT="${2:-}"
      shift 2
      ;;
    --delay)
      DELAY_SEC="${2:-}"
      shift 2
      ;;
    --resume)
      MODE_RESUME=true
      shift
      ;;
    --fail-fast)
      MODE_FAIL_FAST=true
      shift
      ;;
    --force)
      FLAG_FORCE=true
      shift
      ;;
    --dry-run)
      FLAG_DRY_RUN=true
      shift
      ;;
    --discover-only)
      FLAG_DISCOVER_ONLY=true
      shift
      ;;
    --use-browser)
      FLAG_USE_BROWSER=true
      shift
      ;;
    --debug-html)
      FLAG_DEBUG_HTML=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1"
      usage
      exit 1
      ;;
  esac
done

# Validate arguments
if [[ -z "$TAHUN" || -z "$BULAN" ]]; then
  echo "Error: --yyyy and --mm are required."
  usage
  exit 1
fi

if [[ ! "$TAHUN" =~ ^[0-9]{4}$ ]]; then
  echo "Error: --yyyy must be 4 digits."
  exit 1
fi

if [[ ! "$BULAN" =~ ^(0[1-9]|1[0-2])$ ]]; then
  echo "Error: --mm must be 01..12."
  exit 1
fi

if [[ ! "$TIMEOUT" =~ ^[0-9]+$ ]] || [[ "$TIMEOUT" -le 0 ]]; then
  echo "Error: --timeout must be positive integer."
  exit 1
fi

if [[ ! "$DELAY_SEC" =~ ^[0-9]+$ ]] || [[ "$DELAY_SEC" -lt 0 ]]; then
  echo "Error: --delay must be integer >= 0."
  exit 1
fi

# Setup paths and log
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERIODE="${TAHUN}-${BULAN}"
PERIOD_DIR="${OUTPUT_ROOT}/${PERIODE}"
mkdir -p "$PERIOD_DIR"

LOG_FILE="${PERIOD_DIR}/asuransi_umum_download_log.txt"
FAIL_LOG="${PERIOD_DIR}/asuransi_umum_faildownload_log.txt"
MAIN_SUMMARY="${PERIOD_DIR}/asuransi_umum_summary.md"

# Initialize fail log
> "$FAIL_LOG"

log "INFO" "======================================================================"
log "INFO" "Start Akuisisi Data Asuransi Umum | period=${PERIODE}"
log "INFO" "======================================================================"

DOWNLOAD_SUCCESS=0
DOWNLOAD_FAIL=0
FAILED_COMPANIES=()

# ============================================================================
# PHASE 1: DOWNLOAD PDFs
# ============================================================================
log "INFO" "PHASE 1: Downloading PDFs from Asuransi Umum companies..."
log "INFO" "======================================================================="

COMPANY_SCRIPTS=(
  "pt_aig_insurance_indonesia/pt_aig_insurance_indonesia_download.py"
  "pt_arthagraha_general_insurance/pt_arthagraha_general_insurance_download.py"
  "pt_asuransi_allianz_utama_indonesia/pt_asuransi_allianz_utama_indonesia_download.py"
  "pt_asuransi_artarindo/pt_asuransi_artarindo_download.py"
  "pt_asuransi_asei_indonesia/pt_asuransi_asei_indonesia_download.py"
  "pt_asuransi_astra_buana/pt_asuransi_astra_buana_download.py"
  "pt_asuransi_bangun_askrida/pt_asuransi_bangun_askrida_download.py"
  "pt_asuransi_bhakti_bhayangkara/pt_asuransi_bhakti_bhayangkara_download.py"
  "pt_asuransi_bina_dana_arta_tbk_oona_ins/pt_asuransi_bina_dana_arta_tbk_oona_ins_download.py"
  "pt_asuransi_binagriya_upakara/pt_asuransi_binagriya_upakara_download.py"
  "pt_asuransi_bintang_tbk/pt_asuransi_bintang_tbk_download.py"
  "pt_asuransi_buana_independent/pt_asuransi_buana_independent_download.py"
  "pt_asuransi_cakrawala_proteksi_indonesia/pt_asuransi_cakrawala_proteksi_indonesia_download.py"
  "pt_asuransi_candi_utama/pt_asuransi_candi_utama_download.py"
  "pt_asuransi_central_asia/pt_asuransi_central_asia_download.py"
  "pt_asuransi_dayin_mitra_tbk/pt_asuransi_dayin_mitra_tbk_download.py"
  "pt_asuransi_digital_bersama_tbk/pt_asuransi_digital_bersama_tbk_download.py"
  "pt_asuransi_eka_lloyd_jaya/pt_asuransi_eka_lloyd_jaya_download.py"
  "pt_asuransi_etiqa_internasional_indonesia/pt_asuransi_etiqa_internasional_indonesia_download.py"
  "pt_asuransi_fpg_indonesia/pt_asuransi_fpg_indonesia_download.py"
  "pt_asuransi_harta_aman_pratama_tbk/pt_asuransi_harta_aman_pratama_tbk_download.py"
  "pt_asuransi_intra_asia/pt_asuransi_intra_asia_download.py"
  "pt_asuransi_jasa_indonesia/pt_asuransi_jasa_indonesia_download.py"
  "pt_asuransi_jasa_tania_tbk/pt_asuransi_jasa_tania_tbk_download.py"
  "pt_asuransi_jasaraharja_putera/pt_asuransi_jasaraharja_putera_download.py"
  "pt_asuransi_kerugian_jasa_raharja/pt_asuransi_kerugian_jasa_raharja_download.py"
  "pt_asuransi_kredit_indonesia/pt_asuransi_kredit_indonesia_download.py"
  "pt_asuransi_maximus_graha_persada_tbk/pt_asuransi_maximus_graha_persada_tbk_download.py"
  "pt_asuransi_mitra_pelindung_mustika/pt_asuransi_mitra_pelindung_mustika_download.py"
  "pt_asuransi_msig_indonesia/pt_asuransi_msig_indonesia_download.py"
  "pt_asuransi_multi_artha_guna_tbk/pt_asuransi_multi_artha_guna_tbk_download.py"
  "pt_asuransi_perisai_listrik_nasional/pt_asuransi_perisai_listrik_nasional_download.py"
  "pt_asuransi_raksa_pratikara/pt_asuransi_raksa_pratikara_download.py"
  "pt_asuransi_rama_satria_wibawa/pt_asuransi_rama_satria_wibawa_download.py"
  "pt_asuransi_ramayana_tbk/pt_asuransi_ramayana_tbk_download.py"
  "pt_asuransi_reliance_indonesia/pt_asuransi_reliance_indonesia_download.py"
  "pt_asuransi_sahabat_artha_proteksi/pt_asuransi_sahabat_artha_proteksi_download.py"
  "pt_asuransi_samsung_tugu/pt_asuransi_samsung_tugu_download.py"
  "pt_asuransi_simas_insurtech/pt_asuransi_simas_insurtech_download.py"
  "pt_asuransi_sinar_mas/pt_asuransi_sinar_mas_download.py"
  "pt_asuransi_staco_mandiri/pt_asuransi_staco_mandiri_download.py"
  "pt_asuransi_sumit_oto/pt_asuransi_sumit_oto_download.py"
  "pt_asuransi_tokio_marine_indonesia/pt_asuransi_tokio_marine_indonesia_download.py"
  "pt_asuransi_total_bersama/pt_asuransi_total_bersama_download.py"
  "pt_asuransi_tri_pakarta/pt_asuransi_tri_pakarta_download.py"
  "pt_asuransi_tugu_pratama_indonesia_tbk/pt_asuransi_tugu_pratama_indonesia_tbk_download.py"
  "pt_asuransi_umum_bca/pt_asuransi_umum_bca_download.py"
  "pt_asuransi_umum_bumiputera_muda_1967/pt_asuransi_umum_bumiputera_muda_1967_download.py"
  "pt_asuransi_umum_mega/pt_asuransi_umum_mega_download.py"
  "pt_asuransi_umum_moneeinsure/pt_asuransi_umum_moneeinsure_download.py"
  "pt_asuransi_umum_videi/pt_asuransi_umum_videi_download.py"
  "pt_asuransi_untuk_semua/pt_asuransi_untuk_semua_download.py"
  "pt_asuransi_wahana_tata/pt_asuransi_wahana_tata_download.py"
  "pt_avrist_general_insurance/pt_avrist_general_insurance_download.py"
  "pt_axa_insurance_indonesia/pt_axa_insurance_indonesia_download.py"
  "pt_bosowa_asuransi/pt_bosowa_asuransi_download.py"
  "pt_bri_asuransi_indonesia/pt_bri_asuransi_indonesia_download.py"
  "pt_china_taiping_insurance_indonesia/pt_china_taiping_insurance_indonesia_download.py"
  "pt_chubb_general_insurance_indonesia/pt_chubb_general_insurance_indonesia_download.py"
  "pt_citra_international_underwriters/pt_citra_international_underwriters_download.py"
  "pt_great_eastern_general_insurance_indonesia/pt_great_eastern_general_insurance_indonesia_download.py"
  "pt_kookmin_best_insurance_indonesia/pt_kookmin_best_insurance_indonesia_download.py"
  "pt_lippo_general_insurance_tbk/pt_lippo_general_insurance_tbk_download.py"
  "pt_malacca_trust_wuwungan_insurance_tbk/pt_malacca_trust_wuwungan_insurance_tbk_download.py"
  "pt_meritz_korindo_insurance/pt_meritz_korindo_insurance_download.py"
  "pt_mnc_asuransi_indonesia/pt_mnc_asuransi_indonesia_download.py"
  "pt_pan_pacific_insurance/pt_pan_pacific_insurance_download.py"
  "pt_sompo_insurance_indonesia/pt_sompo_insurance_indonesia_download.py"
  "pt_sunday_insurance_indonesia/pt_sunday_insurance_indonesia_download.py"
  "pt_victoria_insurance_tbk/pt_victoria_insurance_tbk_download.py"
  "pt_zurich_asuransi_indonesia_tbk/pt_zurich_asuransi_indonesia_tbk_download.py"
)

TOTAL_COUNT="${#COMPANY_SCRIPTS[@]}"
INDEX=0

for script_name in "${COMPANY_SCRIPTS[@]}"; do
  INDEX=$((INDEX + 1))
  script_path="${SCRIPT_DIR}/${script_name}"

  if [[ ! -f "$script_path" ]]; then
    log "ERROR" "[$INDEX/$TOTAL_COUNT] ${script_name} -> FAIL (script_not_found)"
    FAILED_COMPANIES+=("${company_snake} - script_not_found")
    echo "[$INDEX/$TOTAL_COUNT] ${company_snake} - script_not_found" >> "$FAIL_LOG"
    DOWNLOAD_FAIL=$((DOWNLOAD_FAIL + 1))
    if [[ "$MODE_FAIL_FAST" == "true" ]]; then
      break
    fi
    continue
  fi

  company_snake="$(basename "${script_name%_download.py}")"
  company_dir="${PERIOD_DIR}/asuransi_umum/${company_snake}"
  pdf_path="${company_dir}/${company_snake}_${TAHUN}_${BULAN}.pdf"

  if [[ "$MODE_RESUME" == "true" && -f "$pdf_path" && "$FLAG_FORCE" == "false" ]]; then
    log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SKIP (resume_skip_existing_pdf)"
    DOWNLOAD_SUCCESS=$((DOWNLOAD_SUCCESS + 1))
    continue
  fi

  cmd=(
    python "$script_path"
    --year "$TAHUN"
    --month "$((10#$BULAN))"
    --output-root "$OUTPUT_ROOT"
    --timeout "$TIMEOUT"
  )

  [[ "$FLAG_FORCE" == "true" ]] && cmd+=(--force)
  [[ "$FLAG_DRY_RUN" == "true" ]] && cmd+=(--dry-run)
  [[ "$FLAG_DISCOVER_ONLY" == "true" ]] && cmd+=(--discover-only)
  [[ "$FLAG_USE_BROWSER" == "true" ]] && cmd+=(--use-browser)
  [[ "$FLAG_DEBUG_HTML" == "true" ]] && cmd+=(--debug-html)

  log "INFO" "[$INDEX/$TOTAL_COUNT] RUN ${company_snake}"
  if "${cmd[@]}" >> "$LOG_FILE" 2>&1; then
    exit_code=0
  else
    exit_code=$?
  fi

  if [[ "$FLAG_DRY_RUN" == "true" || "$FLAG_DISCOVER_ONLY" == "true" ]]; then
    if [[ "$exit_code" -eq 0 ]]; then
      log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SUCCESS (non_download_mode_ok)"
      DOWNLOAD_SUCCESS=$((DOWNLOAD_SUCCESS + 1))
    else
      log "ERROR" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> FAIL (non_download_mode_failed)"
      FAILED_COMPANIES+=("${company_snake} - discovery_failed")
      echo "[$INDEX/$TOTAL_COUNT] ${company_snake} - discovery_failed" >> "$FAIL_LOG"
      DOWNLOAD_FAIL=$((DOWNLOAD_FAIL + 1))
      if [[ "$MODE_FAIL_FAST" == "true" ]]; then
        break
      fi
    fi
  else
    if [[ "$exit_code" -eq 0 && -f "$pdf_path" ]]; then
      log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SUCCESS (pdf_ready)"
      DOWNLOAD_SUCCESS=$((DOWNLOAD_SUCCESS + 1))
    else
      log "ERROR" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> FAIL (pdf_download_failed)"
      FAILED_COMPANIES+=("${company_snake} - download_failed")
      echo "[$INDEX/$TOTAL_COUNT] ${company_snake} - download_failed" >> "$FAIL_LOG"
      DOWNLOAD_FAIL=$((DOWNLOAD_FAIL + 1))
      if [[ "$MODE_FAIL_FAST" == "true" ]]; then
        break
      fi
    fi
  fi

  if [[ "$INDEX" -lt "$TOTAL_COUNT" ]]; then
    sleep "$DELAY_SEC"
  fi
done

log "INFO" "PHASE 1 Complete | success=${DOWNLOAD_SUCCESS} fail=${DOWNLOAD_FAIL}"
log "INFO" ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================
log "INFO" "======================================================================"
log "INFO" "Akuisisi Data Asuransi Umum Complete"
log "INFO" "======================================================================"

{
  echo "# Data Acquisition Summary Asuransi Umum ${PERIODE}"
  echo ""
  echo "## Phase 1: Download PDFs"
  echo "- Success: ${DOWNLOAD_SUCCESS}"
  echo "- Fail: ${DOWNLOAD_FAIL}"
  echo "- Total: $TOTAL_COUNT"
  echo "- Success Rate: $((DOWNLOAD_SUCCESS * 100 / TOTAL_COUNT))%"
  echo ""
  echo "## Details"
  echo "- Period: ${PERIODE}"
  echo "- Output Root: ${OUTPUT_ROOT}"
  echo "- Resume Mode: ${MODE_RESUME}"
  echo "- Download Log: ${LOG_FILE}"
  echo "- Fail Log: ${FAIL_LOG}"
  echo "- Timestamp: $(date)"
  echo ""

  if [[ ${#FAILED_COMPANIES[@]} -gt 0 ]]; then
    echo "## Failed Companies (${#FAILED_COMPANIES[@]})"
    for company in "${FAILED_COMPANIES[@]}"; do
      echo "- $company"
    done
  fi
} > "$MAIN_SUMMARY"

cat "$MAIN_SUMMARY"

exit 0
