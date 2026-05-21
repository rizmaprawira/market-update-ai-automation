#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/download/akuisisi_data_reasuransi.sh --yyyy 2026 --mm 03 [options]

Comprehensive data acquisition: Download PDFs + PDF-to-Text conversion with OCR for maipark

Required:
  --yyyy <year>                  4-digit year (e.g. 2026)
  --mm <month>                   2-digit month (01..12)

Optional:
  --output-root <dir>            Output root (default: data)
  --timeout <sec>                Timeout per company downloader (default: 30)
  --delay <sec>                  Delay between companies (default: 2)
  --mamba-cache-home <dir>       Cache home for mamba lockfiles (default: /tmp/market-update-mamba-cache)
  --resume                       Skip existing PDFs/TXTs
  --fail-fast                    Stop on first failure
  --force                        Overwrite existing PDFs
  --dry-run                      Test run without actual download/conversion
  --discover-only                Discover reports without downloading
  --use-browser                  Use browser rendering for discovery
  --debug-html                   Save HTML debug files
  --skip-nusantara               Skip PT Reasuransi Nusantara Makmur
  --skip-download                Skip download phase, only do pdftotext
  --skip-pdftotext               Skip pdftotext phase, only download
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
FLAG_SKIP_NUSANTARA=false
FLAG_SKIP_DOWNLOAD=false
FLAG_SKIP_PDFTOTEXT=false

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
    --skip-nusantara)
      FLAG_SKIP_NUSANTARA=true
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
  echo "Error: ocrmypdf command not found (required for maipark OCR)."
  exit 1
fi

# Setup paths and log
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERIODE="${TAHUN}-${BULAN}"
PERIOD_DIR="${OUTPUT_ROOT}/${PERIODE}"
mkdir -p "$PERIOD_DIR"
mkdir -p "$MAMBA_CACHE_HOME"

LOG_FILE="${PERIOD_DIR}/akuisisi_log.txt"
MAIN_SUMMARY="${PERIOD_DIR}/akuisisi_summary.md"

log "INFO" "======================================================================"
log "INFO" "Start Akuisisi Data Reasuransi | period=${PERIODE}"
log "INFO" "======================================================================"

DOWNLOAD_SUCCESS=0
DOWNLOAD_FAIL=0
PDFTOTEXT_SUCCESS=0
PDFTOTEXT_FAIL=0

# ============================================================================
# PHASE 1: DOWNLOAD PDFs
# ============================================================================
if [[ "$FLAG_SKIP_DOWNLOAD" != "true" ]]; then
  log "INFO" "PHASE 1: Downloading PDFs..."
  log "INFO" "======================================================================="

  COMPANY_SCRIPTS=(
    "pt_indoperkasa_suksesjaya_reasuransi_download.py"
    "pt_maskapai_reasuransi_indonesia_download.py"
    "pt_orion_reasuransi_indonesia_download.py"
    "pt_reasuransi_indonesia_utama_download.py"
    "pt_reasuransi_maipark_indonesia_download.py"
    "pt_reasuransi_nasional_indonesia_download.py"
    "pt_reasuransi_nusantara_makmur_download.py"
    "pt_tugu_reasuransi_indonesia_download.py"
  )

  if [[ "$FLAG_SKIP_NUSANTARA" == "true" ]]; then
    FILTERED=()
    for s in "${COMPANY_SCRIPTS[@]}"; do
      if [[ "$s" == "pt_reasuransi_nusantara_makmur_download.py" ]]; then
        continue
      fi
      FILTERED+=("$s")
    done
    COMPANY_SCRIPTS=("${FILTERED[@]}")
  fi

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

    company_snake="${script_name%_download.py}"
    company_dir="${PERIOD_DIR}/${company_snake}"
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
# PHASE 2: PDF to TEXT conversion (with OCR for maipark)
# ============================================================================
if [[ "$FLAG_SKIP_PDFTOTEXT" != "true" && "$FLAG_DRY_RUN" != "true" && "$FLAG_DISCOVER_ONLY" != "true" ]]; then
  log "INFO" "PHASE 2: Converting PDFs to Text (with OCR for maipark)..."
  log "INFO" "======================================================================="

  TOTAL_COUNT=$(find "$PERIOD_DIR" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" | wc -l)

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

      is_maipark=false
      if [[ "$pdf_basename" == *"maipark"* ]]; then
        is_maipark=true
      fi

      exit_code=0
      if [[ "$is_maipark" == "true" ]]; then
        ocr_pdf="${pdf_dir}/${pdf_basename%.pdf}_ocr.pdf"
        log "INFO" "[$INDEX/$TOTAL_COUNT] Running OCR for maipark"
        mkdir -p "$HOME/ocrmypdf_tmp"
        if TMPDIR="$HOME/ocrmypdf_tmp" ocrmypdf --deskew --clean --oversample 400 --tesseract-pagesegmode 1 "$(cd "$(dirname "$pdf_path")" && pwd)/$(basename "$pdf_path")" "$ocr_pdf" >> "$LOG_FILE" 2>&1; then
          log "INFO" "[$INDEX/$TOTAL_COUNT] OCR completed, running pdftotext"
          if pdftotext -layout "$ocr_pdf" "$txt_path" >> "$LOG_FILE" 2>&1; then
            exit_code=0
          else
            exit_code=$?
          fi
        else
          exit_code=$?
          log "WARN" "[$INDEX/$TOTAL_COUNT] OCR failed, trying pdftotext on original PDF"
          if pdftotext -layout "$pdf_path" "$txt_path" >> "$LOG_FILE" 2>&1; then
            exit_code=0
          else
            exit_code=$?
          fi
        fi
      else
        if pdftotext -layout "$pdf_path" "$txt_path" >> "$LOG_FILE" 2>&1; then
          exit_code=0
        else
          exit_code=$?
        fi
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
    done < <(find "$PERIOD_DIR" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" | sort)

    log "INFO" "PHASE 2 Complete | success=${PDFTOTEXT_SUCCESS} fail=${PDFTOTEXT_FAIL}"
  fi
  log "INFO" ""
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================
log "INFO" "======================================================================"
log "INFO" "Akuisisi Data Reasuransi Complete"
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
  echo "## Details"
  echo "- Period: ${PERIODE}"
  echo "- Output Root: ${OUTPUT_ROOT}"
  echo "- Resume Mode: ${MODE_RESUME}"
  echo "- Log File: ${LOG_FILE}"
} > "$MAIN_SUMMARY"

cat "$MAIN_SUMMARY"

exit 0
