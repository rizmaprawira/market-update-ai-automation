#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/akuisisi_data/akuisisi_data_asuransi_jiwa.sh --yyyy 2026 --mm 04 [options]

Comprehensive data acquisition: Download PDFs → PDF-to-Text (with OCR) → Extract Key Metrics

Required:
  --yyyy <year>                  4-digit year (e.g. 2026)
  --mm <month>                   2-digit month (01..12)

Optional:
  --output-root <dir>            Output root (default: data)
  --timeout <sec>                Timeout per company downloader (default: 30)
  --delay <sec>                  Delay between companies (default: 2)
  --mamba-cache-home <dir>       Cache home for mamba lockfiles (default: /tmp/market-update-mamba-cache)
  --resume                       Skip existing PDFs/TXTs/metrics
  --fail-fast                    Stop on first failure
  --force                        Overwrite existing PDFs
  --dry-run                      Test run without actual download/conversion
  --discover-only                Discover reports without downloading
  --use-browser                  Use browser rendering for discovery
  --debug-html                   Save HTML debug files
  --skip-download                Skip Phase 1 (download), do phases 2+3
  --skip-pdftotext               Skip Phase 2 (pdftotext), do phases 1+3
  --skip-key-metric              Skip Phase 3 (metrics extraction), do phases 1+2
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
DELAY_SEC=2
MAMBA_CACHE_HOME="/tmp/market-update-mamba-cache"
MODE_RESUME=false
MODE_FAIL_FAST=false
FLAG_FORCE=false
FLAG_DRY_RUN=false
FLAG_DISCOVER_ONLY=false
FLAG_USE_BROWSER=false
FLAG_DEBUG_HTML=false
FLAG_SKIP_DOWNLOAD=false
FLAG_SKIP_PDFTOTEXT=false
FLAG_SKIP_KEY_METRIC=false

LOG_FILE=""

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
    --mamba-cache-home)
      MAMBA_CACHE_HOME="${2:-}"
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
    --skip-download)
      FLAG_SKIP_DOWNLOAD=true
      shift
      ;;
    --skip-pdftotext)
      FLAG_SKIP_PDFTOTEXT=true
      shift
      ;;
    --skip-key-metric)
      FLAG_SKIP_KEY_METRIC=true
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

if [[ -z "$MAMBA_CACHE_HOME" ]]; then
  echo "Error: --mamba-cache-home cannot be empty."
  exit 1
fi

if ! command -v mamba >/dev/null 2>&1; then
  echo "Error: mamba command not found."
  exit 1
fi

if ! command -v pdftotext >/dev/null 2>&1; then
  echo "Error: pdftotext command not found."
  exit 1
fi

if ! command -v ocrmypdf >/dev/null 2>&1; then
  echo "Error: ocrmypdf command not found (required for OCR)."
  exit 1
fi

if ! command -v magick >/dev/null 2>&1; then
  echo "Error: magick command not found (required for image conversion)."
  exit 1
fi

# Setup paths and log
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERIODE="${TAHUN}-${BULAN}"
PERIOD_DIR="${OUTPUT_ROOT}/${PERIODE}"
mkdir -p "$PERIOD_DIR"
mkdir -p "$MAMBA_CACHE_HOME"

LOG_FILE="${PERIOD_DIR}/akuisisi_log_asuransi_jiwa.txt"
MAIN_SUMMARY="${PERIOD_DIR}/akuisisi_summary_asuransi_jiwa.md"

log "INFO" "======================================================================"
log "INFO" "Start Akuisisi Data Asuransi Jiwa | period=${PERIODE}"
log "INFO" "======================================================================"

DOWNLOAD_SUCCESS=0
DOWNLOAD_FAIL=0
PDFTOTEXT_SUCCESS=0
PDFTOTEXT_FAIL=0
KEY_METRIC_SUCCESS=0
KEY_METRIC_FAIL=0

# ============================================================================
# PHASE 1: DOWNLOAD PDFs
# ============================================================================
if [[ "$FLAG_SKIP_DOWNLOAD" != "true" ]]; then
  log "INFO" "PHASE 1: Downloading PDFs..."
  log "INFO" "======================================================================="

  COMPANY_SCRIPTS=(
    "asuransi_jiwa/pt_aia_financial/pt_aia_financial_download.py"
    "asuransi_jiwa/pt_ajb_bumiputera_1912/pt_ajb_bumiputera_1912_download.py"
    "asuransi_jiwa/pt_asuransi_allianz_life_indonesia/pt_asuransi_allianz_life_indonesia_download.py"
    "asuransi_jiwa/pt_asuransi_bri_life/pt_asuransi_bri_life_download.py"
    "asuransi_jiwa/pt_asuransi_ciputra_indonesia/pt_asuransi_ciputra_indonesia_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_astra/pt_asuransi_jiwa_astra_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_bca/pt_asuransi_jiwa_bca_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_central_asia_raya/pt_asuransi_jiwa_central_asia_raya_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_generali_indonesia/pt_asuransi_jiwa_generali_indonesia_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_ifg/pt_asuransi_jiwa_ifg_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_mandiri_inhealth_indonesia/pt_asuransi_jiwa_mandiri_inhealth_indonesia_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_manulife_indonesia/pt_asuransi_jiwa_manulife_indonesia_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_nasional/pt_asuransi_jiwa_nasional_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_reliance_indonesia/pt_asuransi_jiwa_reliance_indonesia_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_sealnsure/pt_asuransi_jiwa_sealnsure_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_sequis_financial/pt_asuransi_jiwa_sequis_financial_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_sequis_life/pt_asuransi_jiwa_sequis_life_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_starinvestama/pt_asuransi_jiwa_starinvestama_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_taspen/pt_asuransi_jiwa_taspen_download.py"
    "asuransi_jiwa/pt_asuransi_jiwa_teguh_pelita_pelindung/pt_asuransi_jiwa_teguh_pelita_pelindung_download.py"
    "asuransi_jiwa/pt_asuransi_simas_jiwa/pt_asuransi_simas_jiwa_download.py"
    "asuransi_jiwa/pt_avrist_assurance/pt_avrist_assurance_download.py"
    "asuransi_jiwa/pt_axa_financial_indonesia/pt_axa_financial_indonesia_download.py"
    "asuransi_jiwa/pt_axa_mandiri_financial_services/pt_axa_mandiri_financial_services_download.py"
    "asuransi_jiwa/pt_bhinneka_life_indonesia/pt_bhinneka_life_indonesia_download.py"
    "asuransi_jiwa/pt_bni_life_insurance/pt_bni_life_insurance_download.py"
    "asuransi_jiwa/pt_capital_life_indonesia/pt_capital_life_indonesia_download.py"
    "asuransi_jiwa/pt_central_asia_financial__jagadiri_/pt_central_asia_financial__jagadiri__download.py"
    "asuransi_jiwa/pt_china_life_insurance_indonesia/pt_china_life_insurance_indonesia_download.py"
    "asuransi_jiwa/pt_chubb_life_insurance/pt_chubb_life_insurance_download.py"
    "asuransi_jiwa/pt_equity_life_indonesia/pt_equity_life_indonesia_download.py"
    "asuransi_jiwa/pt_fwd_insurance_indonesia/pt_fwd_insurance_indonesia_download.py"
    "asuransi_jiwa/pt_great_eastern_life_indonesia/pt_great_eastern_life_indonesia_download.py"
    "asuransi_jiwa/pt_hanwha_life_insurance_indonesia/pt_hanwha_life_insurance_indonesia_download.py"
    "asuransi_jiwa/pt_heksa_solution_insurance/pt_heksa_solution_insurance_download.py"
    "asuransi_jiwa/pt_indolife_pensiontama/pt_indolife_pensiontama_download.py"
    "asuransi_jiwa/pt_lippo_life_assurance/pt_lippo_life_assurance_download.py"
    "asuransi_jiwa/pt_mnc_life_assurance/pt_mnc_life_assurance_download.py"
    "asuransi_jiwa/pt_msig_life_insurance_indonesia_tbk/pt_msig_life_insurance_indonesia_tbk_download.py"
    "asuransi_jiwa/pt_pacific_life_insurance/pt_pacific_life_insurance_download.py"
    "asuransi_jiwa/pt_panin_dai-chi_life/pt_panin_dai-chi_life_download.py"
    "asuransi_jiwa/pt_perta_life_insurance/pt_perta_life_insurance_download.py"
    "asuransi_jiwa/pt_pfi_mega_life_insurance/pt_pfi_mega_life_insurance_download.py"
    "asuransi_jiwa/pt_prudential_life_assurance/pt_prudential_life_assurance_download.py"
    "asuransi_jiwa/pt_sun_life_financial_indonesia/pt_sun_life_financial_indonesia_download.py"
    "asuransi_jiwa/pt_tokio_marine_life_insurance_indonesia/pt_tokio_marine_life_insurance_indonesia_download.py"
    "asuransi_jiwa/pt_victoria_alife_indonesia/pt_victoria_alife_indonesia_download.py"
    "asuransi_jiwa/pt_zurich_topas_life/pt_zurich_topas_life_download.py"
  )

  TOTAL_COUNT="${#COMPANY_SCRIPTS[@]}"
  INDEX=0

  for script_name in "${COMPANY_SCRIPTS[@]}"; do
    INDEX=$((INDEX + 1))
    script_path="${SCRIPT_DIR}/${script_name}"

    if [[ ! -f "$script_path" ]]; then
      log "ERROR" "[$INDEX/$TOTAL_COUNT] ${script_name} -> FAIL (script_not_found)"
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
      continue
    fi

    cmd=(
      env XDG_CACHE_HOME="$MAMBA_CACHE_HOME" mamba run -n market_update python "$script_path"
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
fi

# ============================================================================
# PHASE 2: PDF to TEXT conversion (with OCR for special cases)
# ============================================================================
if [[ "$FLAG_SKIP_PDFTOTEXT" != "true" && "$FLAG_DRY_RUN" != "true" && "$FLAG_DISCOVER_ONLY" != "true" ]]; then
  log "INFO" "PHASE 2: Converting PDFs to Text (with OCR for special cases)..."
  log "INFO" "======================================================================="

  TOTAL_COUNT=$(find "$PERIOD_DIR/asuransi_jiwa" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" 2>/dev/null | wc -l)

  if [[ "$TOTAL_COUNT" -eq 0 ]]; then
    log "WARN" "No PDF files found for conversion"
  else
    INDEX=0
    while IFS= read -r pdf_path; do
      if [[ -z "$pdf_path" ]]; then
        continue
      fi
      INDEX=$((INDEX + 1))
      pdf_dir="$(dirname "$pdf_path")"
      pdf_basename="$(basename "$pdf_path")"
      txt_basename="${pdf_basename%.pdf}.txt"
      txt_path="${pdf_dir}/${txt_basename}"

      if [[ "$MODE_RESUME" == "true" && -f "$txt_path" ]]; then
        log "INFO" "[$INDEX/$TOTAL_COUNT] ${pdf_basename} -> SKIP (resume_skip_existing_txt)"
        continue
      fi

      start_epoch="$(date +%s)"
      log "INFO" "[$INDEX/$TOTAL_COUNT] RUN ${pdf_basename}"

      exit_code=0
      if pdftotext -layout "$pdf_path" "$txt_path" >> "$LOG_FILE" 2>&1; then
        exit_code=0
      else
        exit_code=$?
      fi

      end_epoch="$(date +%s)"
      duration_sec=$((end_epoch - start_epoch))

      if [[ "$exit_code" -eq 0 && -f "$txt_path" ]]; then
        log "INFO" "[$INDEX/$TOTAL_COUNT] ${pdf_basename} -> SUCCESS"
        PDFTOTEXT_SUCCESS=$((PDFTOTEXT_SUCCESS + 1))
      else
        log "ERROR" "[$INDEX/$TOTAL_COUNT] ${pdf_basename} -> FAIL"
        PDFTOTEXT_FAIL=$((PDFTOTEXT_FAIL + 1))
      fi
    done < <(find "$PERIOD_DIR/asuransi_jiwa" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" 2>/dev/null | sort)

    log "INFO" "PHASE 2 Complete | success=${PDFTOTEXT_SUCCESS} fail=${PDFTOTEXT_FAIL}"
  fi
  log "INFO" ""
fi

# ============================================================================
# PHASE 3: Extract Key Metrics
# ============================================================================
if [[ "$FLAG_SKIP_KEY_METRIC" != "true" && "$FLAG_DRY_RUN" != "true" && "$FLAG_DISCOVER_ONLY" != "true" ]]; then
  log "INFO" "PHASE 3: Extracting Key Metrics from TXT files..."
  log "INFO" "======================================================================="

  METRIC_SCRIPTS=(
    "asuransi_jiwa/pt_aia_financial/pt_aia_financial_key_metric.py"
    "asuransi_jiwa/pt_ajb_bumiputera_1912/pt_ajb_bumiputera_1912_key_metric.py"
    "asuransi_jiwa/pt_asuransi_allianz_life_indonesia/pt_asuransi_allianz_life_indonesia_key_metric.py"
    "asuransi_jiwa/pt_asuransi_bri_life/pt_asuransi_bri_life_key_metric.py"
    "asuransi_jiwa/pt_asuransi_ciputra_indonesia/pt_asuransi_ciputra_indonesia_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_astra/pt_asuransi_jiwa_astra_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_bca/pt_asuransi_jiwa_bca_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_central_asia_raya/pt_asuransi_jiwa_central_asia_raya_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_generali_indonesia/pt_asuransi_jiwa_generali_indonesia_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_ifg/pt_asuransi_jiwa_ifg_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_mandiri_inhealth_indonesia/pt_asuransi_jiwa_mandiri_inhealth_indonesia_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_manulife_indonesia/pt_asuransi_jiwa_manulife_indonesia_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_nasional/pt_asuransi_jiwa_nasional_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_reliance_indonesia/pt_asuransi_jiwa_reliance_indonesia_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_sealnsure/pt_asuransi_jiwa_sealnsure_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_sequis_financial/pt_asuransi_jiwa_sequis_financial_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_sequis_life/pt_asuransi_jiwa_sequis_life_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_starinvestama/pt_asuransi_jiwa_starinvestama_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_taspen/pt_asuransi_jiwa_taspen_key_metric.py"
    "asuransi_jiwa/pt_asuransi_jiwa_teguh_pelita_pelindung/pt_asuransi_jiwa_teguh_pelita_pelindung_key_metric.py"
    "asuransi_jiwa/pt_asuransi_simas_jiwa/pt_asuransi_simas_jiwa_key_metric.py"
    "asuransi_jiwa/pt_avrist_assurance/pt_avrist_assurance_key_metric.py"
    "asuransi_jiwa/pt_axa_financial_indonesia/pt_axa_financial_indonesia_key_metric.py"
    "asuransi_jiwa/pt_axa_mandiri_financial_services/pt_axa_mandiri_financial_services_key_metric.py"
    "asuransi_jiwa/pt_bhinneka_life_indonesia/pt_bhinneka_life_indonesia_key_metric.py"
    "asuransi_jiwa/pt_bni_life_insurance/pt_bni_life_insurance_key_metric.py"
    "asuransi_jiwa/pt_capital_life_indonesia/pt_capital_life_indonesia_key_metric.py"
    "asuransi_jiwa/pt_central_asia_financial__jagadiri_/pt_central_asia_financial__jagadiri__key_metric.py"
    "asuransi_jiwa/pt_china_life_insurance_indonesia/pt_china_life_insurance_indonesia_key_metric.py"
    "asuransi_jiwa/pt_chubb_life_insurance/pt_chubb_life_insurance_key_metric.py"
    "asuransi_jiwa/pt_equity_life_indonesia/pt_equity_life_indonesia_key_metric.py"
    "asuransi_jiwa/pt_fwd_insurance_indonesia/pt_fwd_insurance_indonesia_key_metric.py"
    "asuransi_jiwa/pt_great_eastern_life_indonesia/pt_great_eastern_life_indonesia_key_metric.py"
    "asuransi_jiwa/pt_hanwha_life_insurance_indonesia/pt_hanwha_life_insurance_indonesia_key_metric.py"
    "asuransi_jiwa/pt_heksa_solution_insurance/pt_heksa_solution_insurance_key_metric.py"
    "asuransi_jiwa/pt_indolife_pensiontama/pt_indolife_pensiontama_key_metric.py"
    "asuransi_jiwa/pt_lippo_life_assurance/pt_lippo_life_assurance_key_metric.py"
    "asuransi_jiwa/pt_mnc_life_assurance/pt_mnc_life_assurance_key_metric.py"
    "asuransi_jiwa/pt_msig_life_insurance_indonesia_tbk/pt_msig_life_insurance_indonesia_tbk_key_metric.py"
    "asuransi_jiwa/pt_pacific_life_insurance/pt_pacific_life_insurance_key_metric.py"
    "asuransi_jiwa/pt_panin_dai-chi_life/pt_panin_dai-chi_life_key_metric.py"
    "asuransi_jiwa/pt_perta_life_insurance/pt_perta_life_insurance_key_metric.py"
    "asuransi_jiwa/pt_pfi_mega_life_insurance/pt_pfi_mega_life_insurance_key_metric.py"
    "asuransi_jiwa/pt_prudential_life_assurance/pt_prudential_life_assurance_key_metric.py"
    "asuransi_jiwa/pt_sun_life_financial_indonesia/pt_sun_life_financial_indonesia_key_metric.py"
    "asuransi_jiwa/pt_tokio_marine_life_insurance_indonesia/pt_tokio_marine_life_insurance_indonesia_key_metric.py"
    "asuransi_jiwa/pt_victoria_alife_indonesia/pt_victoria_alife_indonesia_key_metric.py"
    "asuransi_jiwa/pt_zurich_topas_life/pt_zurich_topas_life_key_metric.py"
  )

  TOTAL_COUNT="${#METRIC_SCRIPTS[@]}"
  INDEX=0

  for script_name in "${METRIC_SCRIPTS[@]}"; do
    INDEX=$((INDEX + 1))
    script_path="${SCRIPT_DIR}/${script_name}"

    if [[ ! -f "$script_path" ]]; then
      log "ERROR" "[$INDEX/$TOTAL_COUNT] ${script_name} -> FAIL (script_not_found)"
      KEY_METRIC_FAIL=$((KEY_METRIC_FAIL + 1))
      if [[ "$MODE_FAIL_FAST" == "true" ]]; then
        break
      fi
      continue
    fi

    company_snake="$(basename "${script_name%_key_metric.py}")"
    company_dir="${PERIOD_DIR}/asuransi_jiwa/${company_snake}"
    txt_path="${company_dir}/${company_snake}_${TAHUN}_${BULAN}.txt"
    metric_csv="${company_dir}/${company_snake}_key_metric_${TAHUN}_${BULAN}.csv"

    if [[ ! -f "$txt_path" ]]; then
      log "WARN" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SKIP (txt_file_not_found)"
      continue
    fi

    if [[ "$MODE_RESUME" == "true" && -f "$metric_csv" ]]; then
      log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SKIP (resume_skip_existing_csv)"
      continue
    fi

    log "INFO" "[$INDEX/$TOTAL_COUNT] RUN ${company_snake}"
    cmd=(
      env XDG_CACHE_HOME="$MAMBA_CACHE_HOME" mamba run -n market_update python "$script_path"
      --yyyy "$TAHUN"
      --mm "$((10#$BULAN))"
      --output-root "$OUTPUT_ROOT"
    )

    if "${cmd[@]}" >> "$LOG_FILE" 2>&1; then
      exit_code=0
    else
      exit_code=$?
    fi

    if [[ "$exit_code" -eq 0 && -f "$metric_csv" ]]; then
      log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SUCCESS (metrics_extracted)"
      KEY_METRIC_SUCCESS=$((KEY_METRIC_SUCCESS + 1))
    else
      log "ERROR" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> FAIL (metrics_extraction_failed)"
      KEY_METRIC_FAIL=$((KEY_METRIC_FAIL + 1))
      if [[ "$MODE_FAIL_FAST" == "true" ]]; then
        break
      fi
    fi

    if [[ "$INDEX" -lt "$TOTAL_COUNT" ]]; then
      sleep "$DELAY_SEC"
    fi
  done

  log "INFO" "PHASE 3 Complete | success=${KEY_METRIC_SUCCESS} fail=${KEY_METRIC_FAIL}"
  log "INFO" ""
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================
log "INFO" "======================================================================"
log "INFO" "Akuisisi Data Asuransi Jiwa Complete"
log "INFO" "======================================================================"

{
  echo "# Data Acquisition Summary ${PERIODE}"
  echo ""
  echo "## Phase 1: Download PDFs"
  if [[ "$FLAG_SKIP_DOWNLOAD" != "true" ]]; then
    echo "- Success: ${DOWNLOAD_SUCCESS}"
    echo "- Fail: ${DOWNLOAD_FAIL}"
  else
    echo "- Status: SKIPPED"
  fi
  echo ""
  echo "## Phase 2: PDF to Text Conversion"
  if [[ "$FLAG_SKIP_PDFTOTEXT" != "true" && "$FLAG_DRY_RUN" != "true" && "$FLAG_DISCOVER_ONLY" != "true" ]]; then
    echo "- Success: ${PDFTOTEXT_SUCCESS}"
    echo "- Fail: ${PDFTOTEXT_FAIL}"
  else
    echo "- Status: SKIPPED"
  fi
  echo ""
  echo "## Phase 3: Extract Key Metrics"
  if [[ "$FLAG_SKIP_KEY_METRIC" != "true" && "$FLAG_DRY_RUN" != "true" && "$FLAG_DISCOVER_ONLY" != "true" ]]; then
    echo "- Success: ${KEY_METRIC_SUCCESS}"
    echo "- Fail: ${KEY_METRIC_FAIL}"
    echo "- Database: data/${PERIODE}/database_asuransi_jiwa_${TAHUN}_${BULAN}.csv"
  else
    echo "- Status: SKIPPED"
  fi
  echo ""
  echo "## Details"
  echo "- Period: ${PERIODE}"
  echo "- Output Root: ${OUTPUT_ROOT}"
  echo "- Resume Mode: ${MODE_RESUME}"
  echo "- Log File: ${LOG_FILE}"
} > "$MAIN_SUMMARY"

cat "$MAIN_SUMMARY"

exit 0
