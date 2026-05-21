#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./asuransi_jiwa_download.sh --yyyy 2026 --mm 03 [options]

Download financial reports for Asuransi Jiwa (Life Insurance) companies

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

LOG_FILE="${PERIOD_DIR}/asuransi_jiwa_download_log.txt"
FAIL_LOG="${PERIOD_DIR}/asuransi_jiwa_faildownload_log.txt"
MAIN_SUMMARY="${PERIOD_DIR}/asuransi_jiwa_summary.md"

# Initialize fail log
> "$FAIL_LOG"

log "INFO" "======================================================================"
log "INFO" "Start Akuisisi Data Asuransi Jiwa | period=${PERIODE}"
log "INFO" "======================================================================"

DOWNLOAD_SUCCESS=0
DOWNLOAD_FAIL=0
FAILED_COMPANIES=()

# ============================================================================
# PHASE 1: DOWNLOAD PDFs
# ============================================================================
log "INFO" "PHASE 1: Downloading PDFs from Asuransi Jiwa companies..."
log "INFO" "======================================================================="

COMPANY_SCRIPTS=(
  "pt_aia_financial/pt_aia_financial_download.py"
  "pt_ajb_bumiputera_1912/pt_ajb_bumiputera_1912_download.py"
  "pt_asuransi_allianz_life_indonesia/pt_asuransi_allianz_life_indonesia_download.py"
  "pt_asuransi_bri_life/pt_asuransi_bri_life_download.py"
  "pt_asuransi_ciputra_indonesia/pt_asuransi_ciputra_indonesia_download.py"
  "pt_asuransi_jiwa_astra/pt_asuransi_jiwa_astra_download.py"
  "pt_asuransi_jiwa_bca/pt_asuransi_jiwa_bca_download.py"
  "pt_asuransi_jiwa_central_asia_raya/pt_asuransi_jiwa_central_asia_raya_download.py"
  "pt_asuransi_jiwa_generali_indonesia/pt_asuransi_jiwa_generali_indonesia_download.py"
  "pt_asuransi_jiwa_ifg/pt_asuransi_jiwa_ifg_download.py"
  "pt_asuransi_jiwa_mandiri_inhealth_indonesia/pt_asuransi_jiwa_mandiri_inhealth_indonesia_download.py"
  "pt_asuransi_jiwa_manulife_indonesia/pt_asuransi_jiwa_manulife_indonesia_download.py"
  "pt_asuransi_jiwa_nasional/pt_asuransi_jiwa_nasional_download.py"
  "pt_asuransi_jiwa_reliance_indonesia/pt_asuransi_jiwa_reliance_indonesia_download.py"
  "pt_asuransi_jiwa_sealnsure/pt_asuransi_jiwa_sealnsure_download.py"
  "pt_asuransi_jiwa_sequis_financial/pt_asuransi_jiwa_sequis_financial_download.py"
  "pt_asuransi_jiwa_sequis_life/pt_asuransi_jiwa_sequis_life_download.py"
  "pt_asuransi_jiwa_starinvestama/pt_asuransi_jiwa_starinvestama_download.py"
  "pt_asuransi_jiwa_taspen/pt_asuransi_jiwa_taspen_download.py"
  "pt_asuransi_jiwa_teguh_pelita_pelindung/pt_asuransi_jiwa_teguh_pelita_pelindung_download.py"
  "pt_asuransi_simas_jiwa/pt_asuransi_simas_jiwa_download.py"
  "pt_avrist_assurance/pt_avrist_assurance_download.py"
  "pt_axa_financial_indonesia/pt_axa_financial_indonesia_download.py"
  "pt_axa_mandiri_financial_services/pt_axa_mandiri_financial_services_download.py"
  "pt_bhinneka_life_indonesia/pt_bhinneka_life_indonesia_download.py"
  "pt_bni_life_insurance/pt_bni_life_insurance_download.py"
  "pt_capital_life_indonesia/pt_capital_life_indonesia_download.py"
  "pt_central_asia_financial__jagadiri_/pt_central_asia_financial__jagadiri__download.py"
  "pt_china_life_insurance_indonesia/pt_china_life_insurance_indonesia_download.py"
  "pt_chubb_life_insurance/pt_chubb_life_insurance_download.py"
  "pt_equity_life_indonesia/pt_equity_life_indonesia_download.py"
  "pt_fwd_insurance_indonesia/pt_fwd_insurance_indonesia_download.py"
  "pt_great_eastern_life_indonesia/pt_great_eastern_life_indonesia_download.py"
  "pt_hanwha_life_insurance_indonesia/pt_hanwha_life_insurance_indonesia_download.py"
  "pt_heksa_solution_insurance/pt_heksa_solution_insurance_download.py"
  "pt_indolife_pensiontama/pt_indolife_pensiontama_download.py"
  "pt_lippo_life_assurance/pt_lippo_life_assurance_download.py"
  "pt_mnc_life_assurance/pt_mnc_life_assurance_download.py"
  "pt_msig_life_insurance_indonesia_tbk/pt_msig_life_insurance_indonesia_tbk_download.py"
  "pt_pacific_life_insurance/pt_pacific_life_insurance_download.py"
  "pt_panin_dai-chi_life/pt_panin_dai-chi_life_download.py"
  "pt_perta_life_insurance/pt_perta_life_insurance_download.py"
  "pt_pfi_mega_life_insurance/pt_pfi_mega_life_insurance_download.py"
  "pt_prudential_life_assurance/pt_prudential_life_assurance_download.py"
  "pt_sun_life_financial_indonesia/pt_sun_life_financial_indonesia_download.py"
  "pt_tokio_marine_life_insurance_indonesia/pt_tokio_marine_life_insurance_indonesia_download.py"
  "pt_victoria_alife_indonesia/pt_victoria_alife_indonesia_download.py"
  "pt_zurich_topas_life/pt_zurich_topas_life_download.py"
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
  company_dir="${PERIOD_DIR}/asuransi_jiwa/${company_snake}"
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
log "INFO" "Akuisisi Data Asuransi Jiwa Complete"
log "INFO" "======================================================================"

{
  echo "# Data Acquisition Summary Asuransi Jiwa ${PERIODE}"
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
