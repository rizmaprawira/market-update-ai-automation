#!/usr/bin/env bash

# ============================================================
# akuisisi_data_v3.sh
# Orkestrasi akuisisi laporan keuangan bulanan (current + prior year)
# Output kontrak v3:
#   data/YYYY-MM/
#   ├─ database_konsolidasi.csv
#   ├─ log.txt
#   ├─ .checkpoint_YYYY-MM.txt
#   ├─ summary.md
#   └─ {company_snake_case}/
#       ├─ laporan_keuangan.pdf
#       ├─ {company_snake_case}_raw.json
#       ├─ {company_snake_case}_row.csv
#       └─ status.txt
# ============================================================

set -u
set -o pipefail

# -------------------------------
# Konstanta runtime
# -------------------------------
JUMLAH_KOLOM_CSV=12
MAX_RETRIES=2                      # Retry teknis per URL
RETRY_DELAY_SECONDS=3
DEFAULT_MODEL="gpt-5.5"
DEFAULT_APPROVAL_POLICY="never"
DEFAULT_SANDBOX_MODE="workspace-write"
PROMPT_TEMPLATE_PATH="docs/codex_exec_prompt_v3.txt"
CSV_HEADER="periode|jenis_asuransi|nama_perusahaan|aset|ekuitas|premi_penutupan_tidak_langsung|premi_bruto|pendapatan_premi|hasil_underwriting|laba_rugi_komprehensif|rasio_solvabilitas|rasio_likuiditas"

# -------------------------------
# Variabel flag
# -------------------------------
TAHUN=""
BULAN=""
COMPANIES_FILE=""
MODEL_NAME="$DEFAULT_MODEL"
APPROVAL_POLICY="$DEFAULT_APPROVAL_POLICY"
SANDBOX_MODE="$DEFAULT_SANDBOX_MODE"
DELAY_DETIK=5
MODE_RESUME=false
MODE_FAIL_FAST=false

# -------------------------------
# Utilitas logging
# -------------------------------
LOG_FILE=""

log_info() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] [INFO] $msg"
  [[ -n "$LOG_FILE" ]] && echo "[$ts] [INFO] $msg" >> "$LOG_FILE"
}

log_warn() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] [WARN] $msg"
  [[ -n "$LOG_FILE" ]] && echo "[$ts] [WARN] $msg" >> "$LOG_FILE"
}

log_error() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] [ERROR] $msg"
  [[ -n "$LOG_FILE" ]] && echo "[$ts] [ERROR] $msg" >> "$LOG_FILE"
}

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/akuisisi_data_v3.sh --YYYY 2026 --MM 04 --companies config/link_reasuransi.txt [options]

Flags wajib:
  --YYYY <tahun>            Tahun 4 digit, contoh: 2026
  --MM <bulan>              Bulan 2 digit, contoh: 04
  --companies <file>        File URL input (1 URL per line, boleh ada komentar #)

Flags opsional:
  --model <nama_model>      Model Codex (default: gpt-5.5)
  --approval-policy <mode>  Approval policy Codex: untrusted|on-request|on-failure|never (default: never)
  --sandbox <mode>          Sandbox Codex: read-only|workspace-write|danger-full-access (default: workspace-write)
  --delay <detik>           Jeda antar URL (default: 5)
  --resume                  Skip URL yang sudah di-checkpoint
  --fail-fast               Hentikan seluruh run jika satu URL gagal permanen
  --help                    Tampilkan bantuan
USAGE
}

normalize_url() {
  # Normalisasi ringan agar checkpoint match lebih konsisten.
  local url="$1"
  url="${url#${url%%[![:space:]]*}}"
  url="${url%${url##*[![:space:]]}}"
  echo "$url"
}

url_domain() {
  local url="$1"
  local d
  d="$(echo "$url" | sed -E 's#^https?://##; s#/.*$##; s#^www\.##')"
  echo "$d"
}

slugify() {
  local s="$1"
  s="$(echo "$s" | tr '[:upper:]' '[:lower:]')"
  s="$(echo "$s" | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//')"
  echo "$s"
}

company_snake_from_url() {
  local url="$1"
  local domain
  domain="$(url_domain "$url")"

  case "$domain" in
    inare.co.id)
      echo "pt_indoperkasa_suksesjaya_reasuransi"
      ;;
    marein-re.com)
      echo "pt_maskapai_reasuransi_indonesia"
      ;;
    orionre.id)
      echo "pt_orion_reasuransi_indonesia"
      ;;
    indonesiare.co.id)
      echo "pt_reasuransi_indonesia_utama"
      ;;
    maipark.com)
      echo "pt_reasuransi_maipark_indonesia"
      ;;
    nasionalre.id)
      echo "pt_reasuransi_nasional_indonesia"
      ;;
    nusantarare.com)
      echo "pt_reasuransi_nusantara_makmur"
      ;;
    tugure.id)
      echo "pt_tugu_reasuransi_indonesia"
      ;;
    *)
      # Fallback generik untuk URL baru di scale-up.
      echo "$(slugify "pt_${domain}")"
      ;;
  esac
}

ensure_json_error_stub() {
  local json_file="$1"
  local website_url="$2"
  local periode="$3"
  local reason="$4"

  if [[ -f "$json_file" && -s "$json_file" ]]; then
    return 0
  fi

  cat > "$json_file" <<EOF_JSON
{
  "extraction_metadata": {
    "extracted_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "source_url": "$website_url",
    "target_periode": "$periode",
    "extraction_status": "failed"
  },
  "raw_text": "",
  "sections": {},
  "key_metrics": {},
  "extraction_notes": {
    "error": "$reason",
    "sections_found": [],
    "sections_not_found": ["all"],
    "missing_fields": {}
  }
}
EOF_JSON
}

status_from_file() {
  local status_file="$1"
  if [[ ! -f "$status_file" ]]; then
    echo ""
    return 0
  fi
  tr -d '[:space:]' < "$status_file"
}

is_valid_status() {
  local s="$1"
  case "$s" in
    BERHASIL|PARSIAL|TIDAK_DITEMUKAN|GAGAL)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

csv_has_na() {
  local csv_file="$1"
  awk -F'|' '
    {
      for (i=1; i<=NF; i++) {
        if ($i == "N/A") { found=1 }
      }
    }
    END { exit(found ? 0 : 1) }
  ' "$csv_file"
}

validate_company_csv() {
  local csv_file="$1"
  local periode_current="$2"
  local periode_prior="$3"

  [[ -f "$csv_file" && -s "$csv_file" ]] || return 1

  # Ambil baris data saja; toleran bila ada header dari model.
  local rows=()
  local _row=""
  while IFS= read -r _row; do
    rows+=("$_row")
  done < <(grep -vE '^(periode\||tahun-bulan\||[[:space:]]*$)' "$csv_file")

  [[ "${#rows[@]}" -eq 2 ]] || return 1

  local i=0
  while [[ $i -lt 2 ]]; do
    local row="${rows[$i]}"
    local expected_periode="$periode_current"
    [[ $i -eq 1 ]] && expected_periode="$periode_prior"

    local nf
    nf="$(awk -F'|' 'NR==1{print NF}' <<< "$row")"
    [[ "$nf" -eq "$JUMLAH_KOLOM_CSV" ]] || return 1

    local first_col
    first_col="$(cut -d'|' -f1 <<< "$row")"
    [[ "$first_col" == "$expected_periode" ]] || return 1

    i=$((i + 1))
  done

  return 0
}

append_csv_if_valid() {
  local csv_company="$1"
  local csv_konsolidasi="$2"

  local rows=()
  local _row=""
  while IFS= read -r _row; do
    rows+=("$_row")
  done < <(grep -vE '^(periode\||tahun-bulan\||[[:space:]]*$)' "$csv_company")

  local appended=0
  local duplicated=0
  local row
  for row in "${rows[@]}"; do
    if grep -Fxq "$row" "$csv_konsolidasi"; then
      duplicated=$((duplicated + 1))
      continue
    fi
    echo "$row" >> "$csv_konsolidasi"
    appended=$((appended + 1))
  done

  echo "$appended|$duplicated"
}

render_prompt() {
  local template_file="$1"
  local website_url="$2"
  local tahun="$3"
  local bulan="$4"
  local periode="$5"
  local periode_prior="$6"
  local output_dir="$7"
  local company_dir="$8"
  local company_snake="$9"
  local json_output_file="${10}"
  local csv_output_file="${11}"
  local status_file="${12}"

  local content
  content="$(cat "$template_file")"

  content="${content//\{WEBSITE_URL\}/$website_url}"
  content="${content//\{TAHUN\}/$tahun}"
  content="${content//\{BULAN\}/$bulan}"
  content="${content//\{PERIODE\}/$periode}"
  content="${content//\{PERIODE_PRIOR\}/$periode_prior}"
  content="${content//\{OUTPUT_DIR\}/$output_dir}"
  content="${content//\{COMPANY_DIR\}/$company_dir}"
  content="${content//\{COMPANY_SNAKE_CASE\}/$company_snake}"
  content="${content//\{JSON_OUTPUT_FILE\}/$json_output_file}"
  content="${content//\{CSV_OUTPUT_FILE\}/$csv_output_file}"
  content="${content//\{STATUS_FILE\}/$status_file}"

  printf '%s' "$content"
}

# -------------------------------
# Parse argumen
# -------------------------------
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
    --companies)
      COMPANIES_FILE="${2:-}"
      shift 2
      ;;
    --model)
      MODEL_NAME="${2:-}"
      shift 2
      ;;
    --approval-policy)
      APPROVAL_POLICY="${2:-}"
      shift 2
      ;;
    --sandbox)
      SANDBOX_MODE="${2:-}"
      shift 2
      ;;
    --delay)
      DELAY_DETIK="${2:-}"
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
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Flag tidak dikenal: $1"
      usage
      exit 1
      ;;
  esac
done

# -------------------------------
# Validasi awal
# -------------------------------
if [[ -z "$TAHUN" || -z "$BULAN" || -z "$COMPANIES_FILE" ]]; then
  echo "Error: --YYYY, --MM, dan --companies wajib diisi."
  usage
  exit 1
fi

if [[ ! "$TAHUN" =~ ^[0-9]{4}$ ]]; then
  echo "Error: --YYYY harus 4 digit."
  exit 1
fi

if [[ ! "$BULAN" =~ ^(0[1-9]|1[0-2])$ ]]; then
  echo "Error: --MM harus 01-12."
  exit 1
fi

if [[ ! "$DELAY_DETIK" =~ ^[0-9]+$ ]]; then
  echo "Error: --delay harus integer >= 0."
  exit 1
fi

case "$APPROVAL_POLICY" in
  untrusted|on-request|on-failure|never)
    ;;
  *)
    echo "Error: --approval-policy tidak valid. Gunakan: untrusted|on-request|on-failure|never"
    exit 1
    ;;
esac

case "$SANDBOX_MODE" in
  read-only|workspace-write|danger-full-access)
    ;;
  *)
    echo "Error: --sandbox tidak valid. Gunakan: read-only|workspace-write|danger-full-access"
    exit 1
    ;;
esac

if [[ ! -f "$COMPANIES_FILE" ]]; then
  echo "Error: file companies tidak ditemukan: $COMPANIES_FILE"
  exit 1
fi

if [[ ! -f "$PROMPT_TEMPLATE_PATH" ]]; then
  echo "Error: template prompt tidak ditemukan: $PROMPT_TEMPLATE_PATH"
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "Error: perintah 'codex' tidak ditemukan di PATH."
  exit 1
fi

# -------------------------------
# Setup periode output
# -------------------------------
TAHUN_MINUS_1="$((10#$TAHUN - 1))"
PERIODE="${TAHUN}-${BULAN}"
PERIODE_PRIOR="${TAHUN_MINUS_1}-${BULAN}"
PERIOD_DIR="data/${PERIODE}"

CSV_KONSOLIDASI="${PERIOD_DIR}/database_konsolidasi.csv"
LOG_FILE="${PERIOD_DIR}/log.txt"
CHECKPOINT_FILE="${PERIOD_DIR}/.checkpoint_${PERIODE}.txt"
SUMMARY_FILE="${PERIOD_DIR}/summary.md"

mkdir -p "$PERIOD_DIR"

if [[ ! -f "$CSV_KONSOLIDASI" ]]; then
  echo "$CSV_HEADER" > "$CSV_KONSOLIDASI"
fi

if [[ ! -f "$LOG_FILE" ]]; then
  touch "$LOG_FILE"
fi

log_info "============================================================"
log_info "Mulai akuisisi v3 | periode=${PERIODE} | model=${MODEL_NAME}"
log_info "companies_file=${COMPANIES_FILE} | resume=${MODE_RESUME} | fail_fast=${MODE_FAIL_FAST} | delay=${DELAY_DETIK}s | approval=${APPROVAL_POLICY} | sandbox=${SANDBOX_MODE}"
log_info "output_period_dir=${PERIOD_DIR}"
log_info "============================================================"

# Muat daftar URL aktif (skip komentar/baris kosong)
URLS=()
while IFS= read -r _url_line; do
  URLS+=("$_url_line")
done < <(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$COMPANIES_FILE")
TOTAL="${#URLS[@]}"

if [[ "$TOTAL" -eq 0 ]]; then
  log_error "Tidak ada URL aktif di file: $COMPANIES_FILE"
  exit 1
fi

# Counter summary
CNT_BERHASIL=0
CNT_PARSIAL=0
CNT_NOT_FOUND=0
CNT_GAGAL=0
CNT_DILEWATI=0

log_info "Total URL aktif: $TOTAL"

# -------------------------------
# Loop utama per URL
# -------------------------------
INDEX=0
for raw_url in "${URLS[@]}"; do
  INDEX=$((INDEX + 1))
  WEBSITE_URL="$(normalize_url "$raw_url")"

  if [[ -z "$WEBSITE_URL" ]]; then
    continue
  fi

  if [[ "$MODE_RESUME" == "true" ]] && [[ -f "$CHECKPOINT_FILE" ]] && grep -Fqx "SUCCESS:${WEBSITE_URL}" "$CHECKPOINT_FILE"; then
    log_info "[$INDEX/$TOTAL] SKIP (resume checkpoint): $WEBSITE_URL"
    CNT_DILEWATI=$((CNT_DILEWATI + 1))
    continue
  fi

  COMPANY_SNAKE_CASE="$(company_snake_from_url "$WEBSITE_URL")"
  COMPANY_DIR="${PERIOD_DIR}/${COMPANY_SNAKE_CASE}"
  JSON_OUTPUT_FILE="${COMPANY_DIR}/${COMPANY_SNAKE_CASE}_raw.json"
  CSV_OUTPUT_FILE="${COMPANY_DIR}/${COMPANY_SNAKE_CASE}_row.csv"
  STATUS_FILE="${COMPANY_DIR}/status.txt"

  mkdir -p "$COMPANY_DIR"

  # Bersihkan artefak run sebelumnya agar evaluasi tidak false-positive.
  rm -f "$JSON_OUTPUT_FILE" "$CSV_OUTPUT_FILE" "$STATUS_FILE"

  log_info "------------------------------------------------------------"
  log_info "[$INDEX/$TOTAL] START $WEBSITE_URL"
  log_info "company=${COMPANY_SNAKE_CASE} dir=${COMPANY_DIR}"

  PROMPT="$(render_prompt \
    "$PROMPT_TEMPLATE_PATH" \
    "$WEBSITE_URL" \
    "$TAHUN" \
    "$BULAN" \
    "$PERIODE" \
    "$PERIODE_PRIOR" \
    "$PERIOD_DIR" \
    "$COMPANY_DIR" \
    "$COMPANY_SNAKE_CASE" \
    "$JSON_OUTPUT_FILE" \
    "$CSV_OUTPUT_FILE" \
    "$STATUS_FILE")"

  ATTEMPT=1
  MAX_ATTEMPTS=$((MAX_RETRIES + 1))
  FINAL_STATUS=""
  FINAL_EXIT_CODE=0

  while [[ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]]; do
    log_info "[$INDEX/$TOTAL] Attempt ${ATTEMPT}/${MAX_ATTEMPTS} -> $WEBSITE_URL"

    START_TS="$(date +%s)"
    if printf '%s' "$PROMPT" | codex --ask-for-approval "$APPROVAL_POLICY" exec --skip-git-repo-check --model "$MODEL_NAME" --sandbox "$SANDBOX_MODE" - 2>&1 | tee -a "$LOG_FILE"; then
      FINAL_EXIT_CODE=0
    else
      FINAL_EXIT_CODE=$?
      log_warn "Codex exit code=${FINAL_EXIT_CODE} pada attempt ${ATTEMPT}/${MAX_ATTEMPTS}"
    fi
    END_TS="$(date +%s)"
    DURASI=$((END_TS - START_TS))

    FINAL_STATUS="$(status_from_file "$STATUS_FILE")"

    if [[ "$FINAL_EXIT_CODE" -eq 0 ]] && is_valid_status "$FINAL_STATUS"; then
      if [[ "$FINAL_STATUS" == "GAGAL" ]]; then
        log_warn "Status GAGAL terdeteksi di attempt ${ATTEMPT}; akan retry jika slot masih ada."
      else
        log_info "Attempt selesai dengan status=$FINAL_STATUS dalam ${DURASI}s"
        break
      fi
    fi

    if [[ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]]; then
      log_warn "Retry dijadwalkan ${RETRY_DELAY_SECONDS}s lagi (status='${FINAL_STATUS:-none}', exit=${FINAL_EXIT_CODE})."
      sleep "$RETRY_DELAY_SECONDS"
    fi

    ATTEMPT=$((ATTEMPT + 1))
  done

  # Evaluasi final status setelah retry selesai.
  FINAL_STATUS="$(status_from_file "$STATUS_FILE")"
  if ! is_valid_status "$FINAL_STATUS"; then
    FINAL_STATUS="GAGAL"
    echo "$FINAL_STATUS" > "$STATUS_FILE"
    ensure_json_error_stub "$JSON_OUTPUT_FILE" "$WEBSITE_URL" "$PERIODE" "status_file tidak valid atau tidak tersedia setelah retry"
  fi

  case "$FINAL_STATUS" in
    BERHASIL|PARSIAL)
      if ! validate_company_csv "$CSV_OUTPUT_FILE" "$PERIODE" "$PERIODE_PRIOR"; then
        log_error "CSV per-company tidak valid (wajib 2 baris x 12 kolom + periode benar)."
        FINAL_STATUS="GAGAL"
        echo "$FINAL_STATUS" > "$STATUS_FILE"
        ensure_json_error_stub "$JSON_OUTPUT_FILE" "$WEBSITE_URL" "$PERIODE" "CSV output tidak valid"
      fi
      ;;
    TIDAK_DITEMUKAN)
      ensure_json_error_stub "$JSON_OUTPUT_FILE" "$WEBSITE_URL" "$PERIODE" "Laporan periode tidak ditemukan"
      ;;
    GAGAL)
      ensure_json_error_stub "$JSON_OUTPUT_FILE" "$WEBSITE_URL" "$PERIODE" "Gagal permanen setelah retry"
      ;;
  esac

  # Konsistensi status dengan isi CSV (N/A => minimal PARSIAL).
  if [[ "$FINAL_STATUS" == "BERHASIL" ]] && [[ -f "$CSV_OUTPUT_FILE" ]] && csv_has_na "$CSV_OUTPUT_FILE"; then
    FINAL_STATUS="PARSIAL"
    echo "$FINAL_STATUS" > "$STATUS_FILE"
    log_warn "Status dikoreksi menjadi PARSIAL karena ditemukan N/A di CSV."
  fi

  # Append ke CSV konsolidasi hanya bila status BERHASIL/PARSIAL dan CSV valid.
  if [[ "$FINAL_STATUS" == "BERHASIL" || "$FINAL_STATUS" == "PARSIAL" ]]; then
    APPEND_RESULT="$(append_csv_if_valid "$CSV_OUTPUT_FILE" "$CSV_KONSOLIDASI")"
    APPENDED_COUNT="${APPEND_RESULT%%|*}"
    DUPLICATED_COUNT="${APPEND_RESULT##*|}"
    log_info "Append CSV konsolidasi: appended=${APPENDED_COUNT}, duplicate_skipped=${DUPLICATED_COUNT}"
  fi

  # Update counter + checkpoint
  case "$FINAL_STATUS" in
    BERHASIL)
      CNT_BERHASIL=$((CNT_BERHASIL + 1))
      echo "SUCCESS:${WEBSITE_URL}" >> "$CHECKPOINT_FILE"
      log_info "[$INDEX/$TOTAL] BERHASIL"
      ;;
    PARSIAL)
      CNT_PARSIAL=$((CNT_PARSIAL + 1))
      echo "SUCCESS:${WEBSITE_URL}" >> "$CHECKPOINT_FILE"
      log_warn "[$INDEX/$TOTAL] PARSIAL"
      ;;
    TIDAK_DITEMUKAN)
      CNT_NOT_FOUND=$((CNT_NOT_FOUND + 1))
      echo "SUCCESS:${WEBSITE_URL}" >> "$CHECKPOINT_FILE"
      log_warn "[$INDEX/$TOTAL] TIDAK_DITEMUKAN"
      ;;
    GAGAL)
      CNT_GAGAL=$((CNT_GAGAL + 1))
      log_error "[$INDEX/$TOTAL] GAGAL"
      if [[ "$MODE_FAIL_FAST" == "true" ]]; then
        log_error "Fail-fast aktif, proses dihentikan."
        break
      fi
      ;;
  esac

  # Jeda antar URL (kecuali item terakhir)
  if [[ "$INDEX" -lt "$TOTAL" ]]; then
    sleep "$DELAY_DETIK"
  fi
done

# -------------------------------
# Summary akhir run
# -------------------------------
SELESAI_AT="$(date '+%Y-%m-%d %H:%M:%S')"
TOTAL_DIPROSES=$((CNT_BERHASIL + CNT_PARSIAL + CNT_NOT_FOUND + CNT_GAGAL + CNT_DILEWATI))

log_info "============================================================"
log_info "SELESAI run v3 @ ${SELESAI_AT}"
log_info "Total item dihitung: ${TOTAL_DIPROSES}"
log_info "BERHASIL=${CNT_BERHASIL} | PARSIAL=${CNT_PARSIAL} | TIDAK_DITEMUKAN=${CNT_NOT_FOUND} | GAGAL=${CNT_GAGAL} | DILEWATI=${CNT_DILEWATI}"
log_info "CSV konsolidasi: ${CSV_KONSOLIDASI}"
log_info "Checkpoint: ${CHECKPOINT_FILE}"
log_info "============================================================"

cat > "$SUMMARY_FILE" <<EOF_SUMMARY
# Summary Run ${PERIODE}

- Waktu selesai: ${SELESAI_AT}
- File input URL: ${COMPANIES_FILE}
- Model Codex: ${MODEL_NAME}
- Approval policy: ${APPROVAL_POLICY}
- Sandbox mode: ${SANDBOX_MODE}
- Mode resume: ${MODE_RESUME}
- Mode fail-fast: ${MODE_FAIL_FAST}
- Retry policy: max ${MAX_RETRIES} retry per URL

## Hasil

- BERHASIL: ${CNT_BERHASIL}
- PARSIAL: ${CNT_PARSIAL}
- TIDAK_DITEMUKAN: ${CNT_NOT_FOUND}
- GAGAL: ${CNT_GAGAL}
- DILEWATI (resume): ${CNT_DILEWATI}

## Artefak

- CSV konsolidasi: ${CSV_KONSOLIDASI}
- Log: ${LOG_FILE}
- Checkpoint: ${CHECKPOINT_FILE}
EOF_SUMMARY

# Exit code run: non-zero kalau ada GAGAL.
if [[ "$CNT_GAGAL" -gt 0 ]]; then
  exit 2
fi

exit 0
