#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/akuisisi_data/akuisisi_data_all.sh --yyyy 2026 --mm 03 [options]

Unified data acquisition for all 3 insurance sectors:
  1. Reasuransi (8 companies)
  2. Asuransi Jiwa (48 companies)
  3. Asuransi Umum (71 companies)

Each sector runs: Download PDFs → PDF-to-Text (with OCR) → Extract Key Metrics

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
  --skip-reasuransi              Skip Reasuransi sector
  --skip-asuransi-jiwa           Skip Asuransi Jiwa sector
  --skip-asuransi-umum           Skip Asuransi Umum sector
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
FLAG_SKIP_REASURANSI=false
FLAG_SKIP_ASURANSI_JIWA=false
FLAG_SKIP_ASURANSI_UMUM=false

LOG_FILE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    --skip-reasuransi)
      FLAG_SKIP_REASURANSI=true
      shift
      ;;
    --skip-asuransi-jiwa)
      FLAG_SKIP_ASURANSI_JIWA=true
      shift
      ;;
    --skip-asuransi-umum)
      FLAG_SKIP_ASURANSI_UMUM=true
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Validate required arguments
if [[ -z "$TAHUN" || -z "$BULAN" ]]; then
  echo "Error: --yyyy and --mm are required" >&2
  usage
  exit 1
fi

# Normalize month to zero-padded format (01-12)
BULAN=$(printf '%02d' "$((10#$BULAN))")

# Create period directory and log file
PERIOD_DIR="$OUTPUT_ROOT/$TAHUN-$(printf '%02d' "$((10#$BULAN))")"
mkdir -p "$PERIOD_DIR"
LOG_FILE="$PERIOD_DIR/akuisisi_all.log"

log "INFO" "=========================================="
log "INFO" "Starting Unified Data Acquisition Pipeline"
log "INFO" "=========================================="
log "INFO" "Period: $TAHUN-$(printf '%02d' "$((10#$BULAN))")"
log "INFO" "Output Root: $OUTPUT_ROOT"
log "INFO" ""

# Build argument string for each sector script
SHARED_ARGS=(
  "--yyyy" "$TAHUN"
  "--mm" "$BULAN"
  "--output-root" "$OUTPUT_ROOT"
  "--timeout" "$TIMEOUT"
  "--delay" "$DELAY_SEC"
  "--mamba-cache-home" "$MAMBA_CACHE_HOME"
)

[[ "$MODE_RESUME" == "true" ]] && SHARED_ARGS+=("--resume")
[[ "$MODE_FAIL_FAST" == "true" ]] && SHARED_ARGS+=("--fail-fast")
[[ "$FLAG_FORCE" == "true" ]] && SHARED_ARGS+=("--force")
[[ "$FLAG_DRY_RUN" == "true" ]] && SHARED_ARGS+=("--dry-run")
[[ "$FLAG_DISCOVER_ONLY" == "true" ]] && SHARED_ARGS+=("--discover-only")
[[ "$FLAG_USE_BROWSER" == "true" ]] && SHARED_ARGS+=("--use-browser")
[[ "$FLAG_DEBUG_HTML" == "true" ]] && SHARED_ARGS+=("--debug-html")
[[ "$FLAG_SKIP_DOWNLOAD" == "true" ]] && SHARED_ARGS+=("--skip-download")
[[ "$FLAG_SKIP_PDFTOTEXT" == "true" ]] && SHARED_ARGS+=("--skip-pdftotext")
[[ "$FLAG_SKIP_KEY_METRIC" == "true" ]] && SHARED_ARGS+=("--skip-key-metric")

# Track overall status
OVERALL_SUCCESS=true
SECTORS_RUN=0
SECTORS_FAILED=0

# Run Reasuransi
if [[ "$FLAG_SKIP_REASURANSI" != "true" ]]; then
  SECTORS_RUN=$((SECTORS_RUN + 1))
  log "INFO" ""
  log "INFO" "========== SECTOR 1: REASURANSI (8 companies) =========="
  log "INFO" "Starting: $SCRIPT_DIR/akuisisi_data_reasuransi.sh"

  if "$SCRIPT_DIR/akuisisi_data_reasuransi.sh" "${SHARED_ARGS[@]}"; then
    log "INFO" "✓ REASURANSI completed successfully"
  else
    log "ERROR" "✗ REASURANSI failed with exit code $?"
    SECTORS_FAILED=$((SECTORS_FAILED + 1))
    OVERALL_SUCCESS=false
    if [[ "$MODE_FAIL_FAST" == "true" ]]; then
      log "ERROR" "Fail-fast mode: stopping pipeline"
      exit 1
    fi
  fi
fi

# Run Asuransi Jiwa
if [[ "$FLAG_SKIP_ASURANSI_JIWA" != "true" ]]; then
  SECTORS_RUN=$((SECTORS_RUN + 1))
  log "INFO" ""
  log "INFO" "========== SECTOR 2: ASURANSI JIWA (48 companies) =========="
  log "INFO" "Starting: $SCRIPT_DIR/akuisisi_data_asuransi_jiwa.sh"

  if "$SCRIPT_DIR/akuisisi_data_asuransi_jiwa.sh" "${SHARED_ARGS[@]}"; then
    log "INFO" "✓ ASURANSI JIWA completed successfully"
  else
    log "ERROR" "✗ ASURANSI JIWA failed with exit code $?"
    SECTORS_FAILED=$((SECTORS_FAILED + 1))
    OVERALL_SUCCESS=false
    if [[ "$MODE_FAIL_FAST" == "true" ]]; then
      log "ERROR" "Fail-fast mode: stopping pipeline"
      exit 1
    fi
  fi
fi

# Run Asuransi Umum
if [[ "$FLAG_SKIP_ASURANSI_UMUM" != "true" ]]; then
  SECTORS_RUN=$((SECTORS_RUN + 1))
  log "INFO" ""
  log "INFO" "========== SECTOR 3: ASURANSI UMUM (71 companies) =========="
  log "INFO" "Starting: $SCRIPT_DIR/akuisisi_data_asuransi_umum.sh"

  if "$SCRIPT_DIR/akuisisi_data_asuransi_umum.sh" "${SHARED_ARGS[@]}"; then
    log "INFO" "✓ ASURANSI UMUM completed successfully"
  else
    log "ERROR" "✗ ASURANSI UMUM failed with exit code $?"
    SECTORS_FAILED=$((SECTORS_FAILED + 1))
    OVERALL_SUCCESS=false
    if [[ "$MODE_FAIL_FAST" == "true" ]]; then
      log "ERROR" "Fail-fast mode: stopping pipeline"
      exit 1
    fi
  fi
fi

# Print summary
log "INFO" ""
log "INFO" "=========================================="
log "INFO" "Unified Pipeline Summary"
log "INFO" "=========================================="
log "INFO" "Sectors run: $SECTORS_RUN"
log "INFO" "Sectors failed: $SECTORS_FAILED"
log "INFO" "Sectors passed: $((SECTORS_RUN - SECTORS_FAILED))"
log "INFO" ""

if [[ "$OVERALL_SUCCESS" == "true" ]]; then
  log "INFO" "✓ All sectors completed successfully"
  log "INFO" "Log file: $LOG_FILE"
  exit 0
else
  log "ERROR" "✗ Some sectors failed. Check individual logs for details."
  log "INFO" "Log file: $LOG_FILE"
  exit 1
fi
