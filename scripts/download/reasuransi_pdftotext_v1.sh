#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/download/reasuransi_pdftotext_v1.sh --YYYY 2026 --MM 04 [options]

Required:
  --YYYY <year>                  4-digit year (e.g. 2026)
  --MM <month>                   2-digit month (01..12)

Optional:
  --output-root <dir>            Output root (default: data)
  --resume                       Skip PDF when .txt already exists
  --dry-run                      Print commands without execution
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
MODE_RESUME=false
MODE_DRY_RUN=false

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
    --resume)
      MODE_RESUME=true
      shift
      ;;
    --dry-run)
      MODE_DRY_RUN=true
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

if [[ -z "$OUTPUT_ROOT" ]]; then
  echo "Error: --output-root cannot be empty."
  exit 1
fi

if ! command -v pdftotext >/dev/null 2>&1; then
  echo "Error: pdftotext command not found."
  exit 1
fi

PERIODE="${TAHUN}-${BULAN}"
PERIOD_DIR="${OUTPUT_ROOT}/${PERIODE}"

if [[ ! -d "$PERIOD_DIR" ]]; then
  echo "Error: period directory not found: $PERIOD_DIR"
  exit 1
fi

LOG_FILE="${PERIOD_DIR}/pdftotext_log.txt"
SUMMARY_CSV="${PERIOD_DIR}/pdftotext_summary.csv"

SUCCESS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TOTAL_COUNT=0

echo "pdf,txt,status,reason,exit_code,duration_sec" > "$SUMMARY_CSV"

log "INFO" "Start pdftotext | period=${PERIODE} | output_root=${OUTPUT_ROOT} | resume=${MODE_RESUME} | dry_run=${MODE_DRY_RUN}"

TOTAL_COUNT=$(find "$PERIOD_DIR" -name "*_pdf.pdf" | wc -l)

if [[ "$TOTAL_COUNT" -eq 0 ]]; then
  log "INFO" "No *_pdf.pdf files found in $PERIOD_DIR"
  echo "# PDFtoText Summary ${PERIODE}" > "${PERIOD_DIR}/pdftotext_summary.md"
  echo "" >> "${PERIOD_DIR}/pdftotext_summary.md"
  echo "- Period: ${PERIODE}" >> "${PERIOD_DIR}/pdftotext_summary.md"
  echo "- Total PDFs: 0" >> "${PERIOD_DIR}/pdftotext_summary.md"
  exit 0
fi

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
    SKIP_COUNT=$((SKIP_COUNT + 1))
    reason="resume_skip_existing_txt"
    log "INFO" "[$INDEX/$TOTAL_COUNT] ${pdf_basename} -> SKIP (${reason})"
    printf '%s\n' "${pdf_path},${txt_path},SKIP,${reason},0,0" >> "$SUMMARY_CSV"
    continue
  fi

  if [[ "$MODE_DRY_RUN" == "true" ]]; then
    log "INFO" "[$INDEX/$TOTAL_COUNT] [DRY-RUN] pdftotext -layout \"${pdf_path}\" \"${txt_path}\""
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    printf '%s\n' "${pdf_path},${txt_path},SUCCESS,dry_run_ok,0,0" >> "$SUMMARY_CSV"
    continue
  fi

  start_epoch="$(date +%s)"

  log "INFO" "[$INDEX/$TOTAL_COUNT] RUN ${pdf_basename}"
  if pdftotext -layout "$pdf_path" "$txt_path" >> "$LOG_FILE" 2>&1; then
    exit_code=0
  else
    exit_code=$?
  fi

  end_epoch="$(date +%s)"
  duration_sec=$((end_epoch - start_epoch))

  if [[ "$exit_code" -eq 0 && -f "$txt_path" ]]; then
    status="SUCCESS"
    reason="txt_ready"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    status="FAIL"
    reason="pdftotext_error"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi

  log "INFO" "[$INDEX/${TOTAL_COUNT}] ${pdf_basename} -> ${status} (${reason})"
  printf '%s\n' "${pdf_path},${txt_path},${status},${reason},${exit_code},${duration_sec}" >> "$SUMMARY_CSV"
done < <(find "$PERIOD_DIR" -name "*_pdf.pdf" | sort)

{
  echo "# PDFtoText Summary ${PERIODE}"
  echo
  echo "- Period: ${PERIODE}"
  echo "- Total PDFs: ${TOTAL_COUNT}"
  echo "- Success: ${SUCCESS_COUNT}"
  echo "- Fail: ${FAIL_COUNT}"
  echo "- Resume skipped: ${SKIP_COUNT}"
  echo "- Log file: ${LOG_FILE}"
  echo "- CSV summary: ${SUMMARY_CSV}"
} > "${PERIOD_DIR}/pdftotext_summary.md"

log "INFO" "Completed | success=${SUCCESS_COUNT} fail=${FAIL_COUNT} skipped=${SKIP_COUNT}"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 2
fi

exit 0
