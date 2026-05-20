#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/download/reasuransi_download_v3.sh --YYYY 2026 --MM 04 [options]

Required:
  --YYYY <year>                  4-digit year (e.g. 2026)
  --MM <month>                   2-digit month (01..12)

Optional:
  --output-root <dir>            Output root (default: data)
  --timeout <sec>                Timeout per company downloader (default: 30)
  --delay <sec>                  Delay between companies (default: 2)
  --mamba-cache-home <dir>       Cache home for mamba lockfiles (default: /tmp/market-update-mamba-cache)
  --resume                       Skip company when target PDF already exists
  --fail-fast                    Stop on first failure
  --force                        Pass --force to Python downloader
  --dry-run                      Pass --dry-run to Python downloader
  --discover-only                Pass --discover-only to Python downloader
  --use-browser                  Pass --use-browser to Python downloader
  --debug-html                   Pass --debug-html to Python downloader
  --skip-nusantara               Skip PT Reasuransi Nusantara Makmur downloader
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

LOG_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --YYYY)
      TAHUN="${2:-}"
      shift 2
      ;;
    --MM)
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

if [[ -z "$TAHUN" || -z "$BULAN" ]]; then
  echo "Error: --YYYY and --MM are required."
  usage
  exit 1
fi

if [[ ! "$TAHUN" =~ ^[0-9]{4}$ ]]; then
  echo "Error: --YYYY must be 4 digits."
  exit 1
fi

if [[ ! "$BULAN" =~ ^(0[1-9]|1[0-2])$ ]]; then
  echo "Error: --MM must be 01..12."
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERIODE="${TAHUN}-${BULAN}"
PERIOD_DIR="${OUTPUT_ROOT}/${PERIODE}"
mkdir -p "$PERIOD_DIR"
mkdir -p "$MAMBA_CACHE_HOME"

LOG_FILE="${PERIOD_DIR}/download_log.txt"
SUMMARY_CSV="${PERIOD_DIR}/download_summary.csv"
SUMMARY_MD="${PERIOD_DIR}/download_summary.md"

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

SUCCESS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TOTAL_COUNT="${#COMPANY_SCRIPTS[@]}"

echo "company,status,reason,exit_code,pdf_path,script,start_at,end_at,duration_sec" > "$SUMMARY_CSV"

log "INFO" "Start downloader | period=${PERIODE} | output_root=${OUTPUT_ROOT} | resume=${MODE_RESUME} | fail_fast=${MODE_FAIL_FAST}"

INDEX=0
for script_name in "${COMPANY_SCRIPTS[@]}"; do
  INDEX=$((INDEX + 1))
  script_path="${SCRIPT_DIR}/${script_name}"

  if [[ ! -f "$script_path" ]]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
    reason="script_not_found"
    log "ERROR" "[$INDEX/$TOTAL_COUNT] ${script_name} -> FAIL (${reason})"
    printf '%s\n' "${script_name%.py},FAIL,${reason},127,,${script_name},,,0" >> "$SUMMARY_CSV"
    if [[ "$MODE_FAIL_FAST" == "true" ]]; then
      break
    fi
    continue
  fi

  company_snake="${script_name%_download.py}"
  company_dir="${PERIOD_DIR}/${company_snake}"
  pdf_path="${company_dir}/${company_snake}_pdf.pdf"

  if [[ "$MODE_RESUME" == "true" && -f "$pdf_path" && "$FLAG_FORCE" == "false" ]]; then
    SKIP_COUNT=$((SKIP_COUNT + 1))
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    reason="resume_skip_existing_pdf"
    log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> SUCCESS (${reason})"
    printf '%s\n' "${company_snake},SUCCESS,${reason},0,${pdf_path},${script_name},,,0" >> "$SUMMARY_CSV"
    if [[ "$INDEX" -lt "$TOTAL_COUNT" ]]; then
      sleep "$DELAY_SEC"
    fi
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

  start_at="$(date '+%Y-%m-%d %H:%M:%S')"
  start_epoch="$(date +%s)"

  log "INFO" "[$INDEX/$TOTAL_COUNT] RUN ${company_snake}"
  if "${cmd[@]}" >> "$LOG_FILE" 2>&1; then
    exit_code=0
  else
    exit_code=$?
  fi

  end_at="$(date '+%Y-%m-%d %H:%M:%S')"
  end_epoch="$(date +%s)"
  duration_sec=$((end_epoch - start_epoch))

  if [[ "$FLAG_DRY_RUN" == "true" || "$FLAG_DISCOVER_ONLY" == "true" ]]; then
    if [[ "$exit_code" -eq 0 ]]; then
      status="SUCCESS"
      reason="non_download_mode_ok"
      SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
      status="FAIL"
      reason="non_download_mode_failed"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
  else
    if [[ "$exit_code" -eq 0 && -f "$pdf_path" ]]; then
      status="SUCCESS"
      reason="pdf_ready"
      SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    elif [[ "$exit_code" -eq 0 && ! -f "$pdf_path" ]]; then
      status="FAIL"
      reason="exit_zero_but_pdf_missing"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    else
      status="FAIL"
      reason="downloader_error"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
  fi

  log "INFO" "[$INDEX/$TOTAL_COUNT] ${company_snake} -> ${status} (${reason})"
  printf '%s\n' "${company_snake},${status},${reason},${exit_code},${pdf_path},${script_name},${start_at},${end_at},${duration_sec}" >> "$SUMMARY_CSV"

  if [[ "$status" == "FAIL" && "$MODE_FAIL_FAST" == "true" ]]; then
    log "ERROR" "Fail-fast active. stopping run."
    break
  fi

  if [[ "$INDEX" -lt "$TOTAL_COUNT" ]]; then
    sleep "$DELAY_SEC"
  fi
done

{
  echo "# Download Summary ${PERIODE}"
  echo
  echo "- Period: ${PERIODE}"
  echo "- Total configured companies: ${TOTAL_COUNT}"
  echo "- Success: ${SUCCESS_COUNT}"
  echo "- Fail: ${FAIL_COUNT}"
  echo "- Resume skipped: ${SKIP_COUNT}"
  echo "- Log file: ${LOG_FILE}"
  echo "- CSV summary: ${SUMMARY_CSV}"
} > "$SUMMARY_MD"

log "INFO" "Completed | success=${SUCCESS_COUNT} fail=${FAIL_COUNT} skipped=${SKIP_COUNT}"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 2
fi

exit 0
