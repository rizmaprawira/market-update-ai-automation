#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/download/reasuransi_pdftotext_v1.sh --yyyy 2026 --mm 04 [options]

Required:
  --yyyy <year>                  4-digit year (e.g. 2026)
  --mm <month>                   2-digit month (01..12)

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

if [[ -z "$OUTPUT_ROOT" ]]; then
  echo "Error: --output-root cannot be empty."
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

TOTAL_COUNT=$(find "$PERIOD_DIR" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" | wc -l)

if [[ "$TOTAL_COUNT" -eq 0 ]]; then
  log "INFO" "No PDF files (format: *_YYYY_MM.pdf) found in $PERIOD_DIR"
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
    is_maipark=false
    if [[ "$pdf_basename" == *"maipark"* ]]; then
      is_maipark=true
    fi
    if [[ "$is_maipark" == "true" ]]; then
      ocr_pdf="${pdf_dir}/${pdf_basename%.pdf}_ocr.pdf"
      log "INFO" "[$INDEX/$TOTAL_COUNT] [DRY-RUN] ocrmypdf --deskew --clean --oversample 400 --tesseract-pagesegmode 1 \"${pdf_path}\" \"${ocr_pdf}\""
      log "INFO" "[$INDEX/$TOTAL_COUNT] [DRY-RUN] pdftotext -layout \"${ocr_pdf}\" \"${txt_path}\""
    else
      log "INFO" "[$INDEX/$TOTAL_COUNT] [DRY-RUN] pdftotext -layout \"${pdf_path}\" \"${txt_path}\""
    fi
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    printf '%s\n' "${pdf_path},${txt_path},SUCCESS,dry_run_ok,0,0" >> "$SUMMARY_CSV"
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
    log "INFO" "[$INDEX/$TOTAL_COUNT] Running OCR for maipark: ocrmypdf"
    mkdir -p "$HOME/ocrmypdf_tmp"
    if TMPDIR="$HOME/ocrmypdf_tmp" ocrmypdf --deskew --clean --oversample 400 --tesseract-pagesegmode 1 "$(cd "$(dirname "$pdf_path")" && pwd)/$(basename "$pdf_path")" "$ocr_pdf" >> "$LOG_FILE" 2>&1; then
      log "INFO" "[$INDEX/$TOTAL_COUNT] OCR completed, running pdftotext on OCR'd PDF"
      if pdftotext -layout "$ocr_pdf" "$txt_path" >> "$LOG_FILE" 2>&1; then
        exit_code=0
      else
        exit_code=$?
      fi
    else
      exit_code=$?
      log "WARN" "[$INDEX/$TOTAL_COUNT] OCR failed, will try pdftotext on original PDF"
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
done < <(find "$PERIOD_DIR" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" | sort)

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
