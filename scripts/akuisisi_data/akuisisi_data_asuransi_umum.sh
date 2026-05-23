#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/akuisisi_data/akuisisi_data_asuransi_umum.sh --yyyy 2026 --mm 04 [options]

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
  echo "Error: ocrmypdf command not found (required for maipark OCR)."
  exit 1
fi

if ! command -v magick >/dev/null 2>&1; then
  echo "Error: magick command not found (required for Jasa Raharja image conversion)."
  exit 1
fi

# Setup paths and log
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERIODE="${TAHUN}-${BULAN}"
PERIOD_DIR="${OUTPUT_ROOT}/${PERIODE}"
mkdir -p "$PERIOD_DIR"
mkdir -p "$MAMBA_CACHE_HOME"

LOG_FILE="${PERIOD_DIR}/akuisisi_log_asuransi_umum.txt"
MAIN_SUMMARY="${PERIOD_DIR}/akuisisi_summary_asuransi_umum.md"

log "INFO" "======================================================================"
log "INFO" "Start Akuisisi Data Asuransi Umum | period=${PERIODE}"
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
    "asuransi_umum/pt_aig_insurance_indonesia/pt_aig_insurance_indonesia_download.py"
    "asuransi_umum/pt_arthagraha_general_insurance/pt_arthagraha_general_insurance_download.py"
    "asuransi_umum/pt_asuransi_allianz_utama_indonesia/pt_asuransi_allianz_utama_indonesia_download.py"
    "asuransi_umum/pt_asuransi_artarindo/pt_asuransi_artarindo_download.py"
    "asuransi_umum/pt_asuransi_asei_indonesia/pt_asuransi_asei_indonesia_download.py"
    "asuransi_umum/pt_asuransi_astra_buana/pt_asuransi_astra_buana_download.py"
    "asuransi_umum/pt_asuransi_bangun_askrida/pt_asuransi_bangun_askrida_download.py"
    "asuransi_umum/pt_asuransi_bhakti_bhayangkara/pt_asuransi_bhakti_bhayangkara_download.py"
    "asuransi_umum/pt_asuransi_bina_dana_arta_tbk_oona_ins/pt_asuransi_bina_dana_arta_tbk_oona_ins_download.py"
    "asuransi_umum/pt_asuransi_binagriya_upakara/pt_asuransi_binagriya_upakara_download.py"
    "asuransi_umum/pt_asuransi_bintang_tbk/pt_asuransi_bintang_tbk_download.py"
    "asuransi_umum/pt_asuransi_buana_independent/pt_asuransi_buana_independent_download.py"
    "asuransi_umum/pt_asuransi_cakrawala_proteksi_indonesia/pt_asuransi_cakrawala_proteksi_indonesia_download.py"
    "asuransi_umum/pt_asuransi_candi_utama/pt_asuransi_candi_utama_download.py"
    "asuransi_umum/pt_asuransi_central_asia/pt_asuransi_central_asia_download.py"
    "asuransi_umum/pt_asuransi_dayin_mitra_tbk/pt_asuransi_dayin_mitra_tbk_download.py"
    "asuransi_umum/pt_asuransi_digital_bersama_tbk/pt_asuransi_digital_bersama_tbk_download.py"
    "asuransi_umum/pt_asuransi_eka_lloyd_jaya/pt_asuransi_eka_lloyd_jaya_download.py"
    "asuransi_umum/pt_asuransi_etiqa_internasional_indonesia/pt_asuransi_etiqa_internasional_indonesia_download.py"
    "asuransi_umum/pt_asuransi_fpg_indonesia/pt_asuransi_fpg_indonesia_download.py"
    "asuransi_umum/pt_asuransi_harta_aman_pratama_tbk/pt_asuransi_harta_aman_pratama_tbk_download.py"
    "asuransi_umum/pt_asuransi_intra_asia/pt_asuransi_intra_asia_download.py"
    "asuransi_umum/pt_asuransi_jasa_indonesia/pt_asuransi_jasa_indonesia_download.py"
    "asuransi_umum/pt_asuransi_jasa_tania_tbk/pt_asuransi_jasa_tania_tbk_download.py"
    "asuransi_umum/pt_asuransi_jasaraharja_putera/pt_asuransi_jasaraharja_putera_download.py"
    "asuransi_umum/pt_asuransi_kerugian_jasa_raharja/pt_asuransi_kerugian_jasa_raharja_download.py"
    "asuransi_umum/pt_asuransi_kredit_indonesia/pt_asuransi_kredit_indonesia_download.py"
    "asuransi_umum/pt_asuransi_maximus_graha_persada_tbk/pt_asuransi_maximus_graha_persada_tbk_download.py"
    "asuransi_umum/pt_asuransi_mitra_pelindung_mustika/pt_asuransi_mitra_pelindung_mustika_download.py"
    "asuransi_umum/pt_asuransi_msig_indonesia/pt_asuransi_msig_indonesia_download.py"
    "asuransi_umum/pt_asuransi_multi_artha_guna_tbk/pt_asuransi_multi_artha_guna_tbk_download.py"
    "asuransi_umum/pt_asuransi_perisai_listrik_nasional/pt_asuransi_perisai_listrik_nasional_download.py"
    "asuransi_umum/pt_asuransi_raksa_pratikara/pt_asuransi_raksa_pratikara_download.py"
    "asuransi_umum/pt_asuransi_rama_satria_wibawa/pt_asuransi_rama_satria_wibawa_download.py"
    "asuransi_umum/pt_asuransi_ramayana_tbk/pt_asuransi_ramayana_tbk_download.py"
    "asuransi_umum/pt_asuransi_reliance_indonesia/pt_asuransi_reliance_indonesia_download.py"
    "asuransi_umum/pt_asuransi_sahabat_artha_proteksi/pt_asuransi_sahabat_artha_proteksi_download.py"
    "asuransi_umum/pt_asuransi_samsung_tugu/pt_asuransi_samsung_tugu_download.py"
    "asuransi_umum/pt_asuransi_simas_insurtech/pt_asuransi_simas_insurtech_download.py"
    "asuransi_umum/pt_asuransi_sinar_mas/pt_asuransi_sinar_mas_download.py"
    "asuransi_umum/pt_asuransi_staco_mandiri/pt_asuransi_staco_mandiri_download.py"
    "asuransi_umum/pt_asuransi_sumit_oto/pt_asuransi_sumit_oto_download.py"
    "asuransi_umum/pt_asuransi_tokio_marine_indonesia/pt_asuransi_tokio_marine_indonesia_download.py"
    "asuransi_umum/pt_asuransi_total_bersama/pt_asuransi_total_bersama_download.py"
    "asuransi_umum/pt_asuransi_tri_pakarta/pt_asuransi_tri_pakarta_download.py"
    "asuransi_umum/pt_asuransi_tugu_pratama_indonesia_tbk/pt_asuransi_tugu_pratama_indonesia_tbk_download.py"
    "asuransi_umum/pt_asuransi_umum_bca/pt_asuransi_umum_bca_download.py"
    "asuransi_umum/pt_asuransi_umum_bumiputera_muda_1967/pt_asuransi_umum_bumiputera_muda_1967_download.py"
    "asuransi_umum/pt_asuransi_umum_mega/pt_asuransi_umum_mega_download.py"
    "asuransi_umum/pt_asuransi_umum_moneeinsure/pt_asuransi_umum_moneeinsure_download.py"
    "asuransi_umum/pt_asuransi_umum_videi/pt_asuransi_umum_videi_download.py"
    "asuransi_umum/pt_asuransi_untuk_semua/pt_asuransi_untuk_semua_download.py"
    "asuransi_umum/pt_asuransi_wahana_tata/pt_asuransi_wahana_tata_download.py"
    "asuransi_umum/pt_avrist_general_insurance/pt_avrist_general_insurance_download.py"
    "asuransi_umum/pt_axa_insurance_indonesia/pt_axa_insurance_indonesia_download.py"
    "asuransi_umum/pt_bosowa_asuransi/pt_bosowa_asuransi_download.py"
    "asuransi_umum/pt_bri_asuransi_indonesia/pt_bri_asuransi_indonesia_download.py"
    "asuransi_umum/pt_china_taiping_insurance_indonesia/pt_china_taiping_insurance_indonesia_download.py"
    "asuransi_umum/pt_chubb_general_insurance_indonesia/pt_chubb_general_insurance_indonesia_download.py"
    "asuransi_umum/pt_citra_international_underwriters/pt_citra_international_underwriters_download.py"
    "asuransi_umum/pt_great_eastern_general_insurance_indonesia/pt_great_eastern_general_insurance_indonesia_download.py"
    "asuransi_umum/pt_kookmin_best_insurance_indonesia/pt_kookmin_best_insurance_indonesia_download.py"
    "asuransi_umum/pt_lippo_general_insurance_tbk/pt_lippo_general_insurance_tbk_download.py"
    "asuransi_umum/pt_malacca_trust_wuwungan_insurance_tbk/pt_malacca_trust_wuwungan_insurance_tbk_download.py"
    "asuransi_umum/pt_meritz_korindo_insurance/pt_meritz_korindo_insurance_download.py"
    "asuransi_umum/pt_mnc_asuransi_indonesia/pt_mnc_asuransi_indonesia_download.py"
    "asuransi_umum/pt_pan_pacific_insurance/pt_pan_pacific_insurance_download.py"
    "asuransi_umum/pt_sompo_insurance_indonesia/pt_sompo_insurance_indonesia_download.py"
    "asuransi_umum/pt_sunday_insurance_indonesia/pt_sunday_insurance_indonesia_download.py"
    "asuransi_umum/pt_victoria_insurance_tbk/pt_victoria_insurance_tbk_download.py"
    "asuransi_umum/pt_zurich_asuransi_indonesia_tbk/pt_zurich_asuransi_indonesia_tbk_download.py"
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
    company_dir="${PERIOD_DIR}/asuransi_umum/${company_snake}"
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
# PHASE 2: PDF to TEXT conversion (with OCR for maipark + Jasa Raharja)
# ============================================================================
if [[ "$FLAG_SKIP_PDFTOTEXT" != "true" && "$FLAG_DRY_RUN" != "true" && "$FLAG_DISCOVER_ONLY" != "true" ]]; then
  log "INFO" "PHASE 2: Converting PDFs to Text (with OCR for special cases)..."
  log "INFO" "======================================================================="

  TOTAL_COUNT=$(find "$PERIOD_DIR/asuransi_umum" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" 2>/dev/null | wc -l)

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

      is_jasa_raharja=false
      is_maipark=false
      if [[ "$pdf_basename" == *"pt_asuransi_kerugian_jasa_raharja"* ]]; then
        is_jasa_raharja=true
      fi
      if [[ "$pdf_basename" == *"maipark"* ]]; then
        is_maipark=true
      fi

      exit_code=0
      if [[ "$is_jasa_raharja" == "true" ]]; then
        magick_pdf="${pdf_dir}/${pdf_basename%.pdf}_magick.pdf"
        log "INFO" "[$INDEX/$TOTAL_COUNT] Converting image-based PDF with ImageMagick"
        if magick "$pdf_path" "$magick_pdf" >> "$LOG_FILE" 2>&1; then
          log "INFO" "[$INDEX/$TOTAL_COUNT] Running OCR on converted PDF"
          ocr_pdf="${pdf_dir}/${pdf_basename%.pdf}_ocr.pdf"
          mkdir -p "$HOME/ocrmypdf_tmp"
          if TMPDIR="$HOME/ocrmypdf_tmp" ocrmypdf --deskew --clean --oversample 400 --tesseract-pagesegmode 1 "$magick_pdf" "$ocr_pdf" >> "$LOG_FILE" 2>&1; then
            log "INFO" "[$INDEX/$TOTAL_COUNT] OCR completed, running pdftotext"
            if pdftotext -layout "$ocr_pdf" "$txt_path" >> "$LOG_FILE" 2>&1; then
              exit_code=0
            else
              exit_code=$?
            fi
          else
            exit_code=$?
            log "WARN" "[$INDEX/$TOTAL_COUNT] OCR failed, trying pdftotext on magick-converted PDF"
            if pdftotext -layout "$magick_pdf" "$txt_path" >> "$LOG_FILE" 2>&1; then
              exit_code=0
            else
              exit_code=$?
            fi
          fi
        else
          exit_code=$?
          log "WARN" "[$INDEX/$TOTAL_COUNT] ImageMagick conversion failed, trying pdftotext on original"
          if pdftotext -layout "$pdf_path" "$txt_path" >> "$LOG_FILE" 2>&1; then
            exit_code=0
          else
            exit_code=$?
          fi
        fi
      elif [[ "$is_maipark" == "true" ]]; then
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
    done < <(find "$PERIOD_DIR/asuransi_umum" -regex ".*_[0-9]\{4\}_[0-9]\{2\}\.pdf" 2>/dev/null | sort)

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
    "asuransi_umum/pt_aig_insurance_indonesia/pt_aig_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_arthagraha_general_insurance/pt_arthagraha_general_insurance_key_metric.py"
    "asuransi_umum/pt_asuransi_allianz_utama_indonesia/pt_asuransi_allianz_utama_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_artarindo/pt_asuransi_artarindo_key_metric.py"
    "asuransi_umum/pt_asuransi_asei_indonesia/pt_asuransi_asei_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_astra_buana/pt_asuransi_astra_buana_key_metric.py"
    "asuransi_umum/pt_asuransi_bangun_askrida/pt_asuransi_bangun_askrida_key_metric.py"
    "asuransi_umum/pt_asuransi_bhakti_bhayangkara/pt_asuransi_bhakti_bhayangkara_key_metric.py"
    "asuransi_umum/pt_asuransi_bina_dana_arta_tbk_oona_ins/pt_asuransi_bina_dana_arta_tbk_oona_ins_key_metric.py"
    "asuransi_umum/pt_asuransi_binagriya_upakara/pt_asuransi_binagriya_upakara_key_metric.py"
    "asuransi_umum/pt_asuransi_bintang_tbk/pt_asuransi_bintang_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_buana_independent/pt_asuransi_buana_independent_key_metric.py"
    "asuransi_umum/pt_asuransi_cakrawala_proteksi_indonesia/pt_asuransi_cakrawala_proteksi_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_candi_utama/pt_asuransi_candi_utama_key_metric.py"
    "asuransi_umum/pt_asuransi_central_asia/pt_asuransi_central_asia_key_metric.py"
    "asuransi_umum/pt_asuransi_dayin_mitra_tbk/pt_asuransi_dayin_mitra_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_digital_bersama_tbk/pt_asuransi_digital_bersama_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_eka_lloyd_jaya/pt_asuransi_eka_lloyd_jaya_key_metric.py"
    "asuransi_umum/pt_asuransi_etiqa_internasional_indonesia/pt_asuransi_etiqa_internasional_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_fpg_indonesia/pt_asuransi_fpg_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_harta_aman_pratama_tbk/pt_asuransi_harta_aman_pratama_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_intra_asia/pt_asuransi_intra_asia_key_metric.py"
    "asuransi_umum/pt_asuransi_jasa_indonesia/pt_asuransi_jasa_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_jasa_tania_tbk/pt_asuransi_jasa_tania_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_jasaraharja_putera/pt_asuransi_jasaraharja_putera_key_metric.py"
    "asuransi_umum/pt_asuransi_kerugian_jasa_raharja/pt_asuransi_kerugian_jasa_raharja_key_metric.py"
    "asuransi_umum/pt_asuransi_kredit_indonesia/pt_asuransi_kredit_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_maximus_graha_persada_tbk/pt_asuransi_maximus_graha_persada_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_mitra_pelindung_mustika/pt_asuransi_mitra_pelindung_mustika_key_metric.py"
    "asuransi_umum/pt_asuransi_msig_indonesia/pt_asuransi_msig_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_multi_artha_guna_tbk/pt_asuransi_multi_artha_guna_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_perisai_listrik_nasional/pt_asuransi_perisai_listrik_nasional_key_metric.py"
    "asuransi_umum/pt_asuransi_raksa_pratikara/pt_asuransi_raksa_pratikara_key_metric.py"
    "asuransi_umum/pt_asuransi_rama_satria_wibawa/pt_asuransi_rama_satria_wibawa_key_metric.py"
    "asuransi_umum/pt_asuransi_ramayana_tbk/pt_asuransi_ramayana_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_reliance_indonesia/pt_asuransi_reliance_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_sahabat_artha_proteksi/pt_asuransi_sahabat_artha_proteksi_key_metric.py"
    "asuransi_umum/pt_asuransi_samsung_tugu/pt_asuransi_samsung_tugu_key_metric.py"
    "asuransi_umum/pt_asuransi_simas_insurtech/pt_asuransi_simas_insurtech_key_metric.py"
    "asuransi_umum/pt_asuransi_sinar_mas/pt_asuransi_sinar_mas_key_metric.py"
    "asuransi_umum/pt_asuransi_staco_mandiri/pt_asuransi_staco_mandiri_key_metric.py"
    "asuransi_umum/pt_asuransi_sumit_oto/pt_asuransi_sumit_oto_key_metric.py"
    "asuransi_umum/pt_asuransi_tokio_marine_indonesia/pt_asuransi_tokio_marine_indonesia_key_metric.py"
    "asuransi_umum/pt_asuransi_total_bersama/pt_asuransi_total_bersama_key_metric.py"
    "asuransi_umum/pt_asuransi_tri_pakarta/pt_asuransi_tri_pakarta_key_metric.py"
    "asuransi_umum/pt_asuransi_tugu_pratama_indonesia_tbk/pt_asuransi_tugu_pratama_indonesia_tbk_key_metric.py"
    "asuransi_umum/pt_asuransi_umum_bca/pt_asuransi_umum_bca_key_metric.py"
    "asuransi_umum/pt_asuransi_umum_bumiputera_muda_1967/pt_asuransi_umum_bumiputera_muda_1967_key_metric.py"
    "asuransi_umum/pt_asuransi_umum_mega/pt_asuransi_umum_mega_key_metric.py"
    "asuransi_umum/pt_asuransi_umum_moneeinsure/pt_asuransi_umum_moneeinsure_key_metric.py"
    "asuransi_umum/pt_asuransi_umum_videi/pt_asuransi_umum_videi_key_metric.py"
    "asuransi_umum/pt_asuransi_untuk_semua/pt_asuransi_untuk_semua_key_metric.py"
    "asuransi_umum/pt_asuransi_wahana_tata/pt_asuransi_wahana_tata_key_metric.py"
    "asuransi_umum/pt_avrist_general_insurance/pt_avrist_general_insurance_key_metric.py"
    "asuransi_umum/pt_axa_insurance_indonesia/pt_axa_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_bosowa_asuransi/pt_bosowa_asuransi_key_metric.py"
    "asuransi_umum/pt_bri_asuransi_indonesia/pt_bri_asuransi_indonesia_key_metric.py"
    "asuransi_umum/pt_china_taiping_insurance_indonesia/pt_china_taiping_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_chubb_general_insurance_indonesia/pt_chubb_general_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_citra_international_underwriters/pt_citra_international_underwriters_key_metric.py"
    "asuransi_umum/pt_great_eastern_general_insurance_indonesia/pt_great_eastern_general_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_kookmin_best_insurance_indonesia/pt_kookmin_best_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_lippo_general_insurance_tbk/pt_lippo_general_insurance_tbk_key_metric.py"
    "asuransi_umum/pt_malacca_trust_wuwungan_insurance_tbk/pt_malacca_trust_wuwungan_insurance_tbk_key_metric.py"
    "asuransi_umum/pt_meritz_korindo_insurance/pt_meritz_korindo_insurance_key_metric.py"
    "asuransi_umum/pt_mnc_asuransi_indonesia/pt_mnc_asuransi_indonesia_key_metric.py"
    "asuransi_umum/pt_pan_pacific_insurance/pt_pan_pacific_insurance_key_metric.py"
    "asuransi_umum/pt_sompo_insurance_indonesia/pt_sompo_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_sunday_insurance_indonesia/pt_sunday_insurance_indonesia_key_metric.py"
    "asuransi_umum/pt_victoria_insurance_tbk/pt_victoria_insurance_tbk_key_metric.py"
    "asuransi_umum/pt_zurich_asuransi_indonesia_tbk/pt_zurich_asuransi_indonesia_tbk_key_metric.py"
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
    company_dir="${PERIOD_DIR}/asuransi_umum/${company_snake}"
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
log "INFO" "Akuisisi Data Asuransi Umum Complete"
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
  echo "## Phase 2: PDF to Text Conversion (with OCR)"
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
    echo "- Database: data/${PERIODE}/database_asuransi_umum_${TAHUN}_${BULAN}.csv"
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
