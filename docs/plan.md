# Summarize Plan - Automated Financial Report Processing

## 🎯 Overall Goal
Akuisisi data laporan keuangan dari 125+ perusahaan asuransi/reasuransi Indonesia untuk periode spesifik (YYYY-MM) dan consolidate ke 1 CSV terpusat.

---

## 📋 Workflow Architecture

### **1. Main Orchestration: `akuisisi_data.sh`**
```bash
./akuisisi_data.sh --2026 --04
```
- Accept flags: `--YYYY --MM` (e.g., `--2026 --04` untuk April 2026)
- Loop through `perusahaan.txt` (125+ URLs)
- Untuk setiap URL:
  - Spawn Claude Code session
  - Send prompt dengan URL + period
  - Capture output
  - Append ke `data_konsolidasi_2026-04.csv`
- Generate log file: `log_2026-04.txt`

---

### **2. Input Data: `perusahaan.txt`**
Simple text file dengan 125+ URLs:
```
https://inare.co.id/en/report/
https://marein-re.com/laporan-keuangan
https://www.orionre.id/id/publikasi.html
https://www.indonesiare.co.id/id/investor-relations/financial-report
https://maipark.com/id/corporate/laporan?financePage=1&yearlyPage=1&type=financial
https://nasionalre.id/laporan-tahunan
https://nusantarare.com/report/?lang=in
https://www.tugure.id/id/financial/financial-report
# ... 117+ more companies
```

---

### **3. Claude Code Prompt (Injected via stdin)**
**Key responsibilities:**
1. **Discover** — dari website, cari & download laporan untuk bulan/tahun yang diminta
2. **Extract** — konvert PDF → JSON (extract semua data finansial)
3. **Transform** — ambil kolom sesuai schema:
   ```
   tahun-bulan | jenis_asuransi | perusahaan | aset | ekuitas | 
   premi_penutupan_tidak_langsung | premi_bruto | pendapatan_premi | 
   hasil_underwriting | laba_rugi_komprehensif | rasio_solvabilitas | rasio_likuiditas
   ```
4. **Output** — generate CSV lokal (1 row data)
5. **Cleanup** — format BAHASA INDONESIA, error handling

---

### **4. Output Structure**

**Per run:**
```
data_konsolidasi_2026-04.csv  ← Main output (125+ rows, 1 per perusahaan)
log_2026-04.txt               ← Processing log (success/fail tracking)
```

**CSV format:**
```
tahun-bulan|jenis_asuransi|perusahaan|aset|ekuitas|...
2026-04|Asuransi Umum|Orion|Rp XXX|Rp XXX|...
2026-04|Reasuransi|INARE|Rp XXX|Rp XXX|...
...
```

---

## 🔄 Execution Flow

```
User runs: ./akuisisi_data.sh --2026 --04
    ↓
Bash script validates flags (YYYY, MM)
    ↓
Initialize data_konsolidasi_2026-04.csv (header only)
    ↓
FOR EACH company URL in perusahaan.txt:
    ├─ Generate Claude Code prompt (URL + 2026-04 injected)
    ├─ Spawn: echo "$PROMPT" | claude
    ├─ Claude discovers & downloads PDF
    ├─ Claude extracts JSON
    ├─ Claude transforms to CSV row
    ├─ Check output file exists
    ├─ Append to data_konsolidasi_2026-04.csv
    ├─ Log success/fail
    └─ Sleep 3s (rate limit)
    ↓
Generate summary:
    ├─ Total processed: 125
    ├─ Success: N
    ├─ Failed: M
    └─ Output file location
```

---

## 📁 File Structure

```
.
├── akuisisi_data.sh          ← Main orchestration script
├── perusahaan.txt            ← 125+ company URLs
├── data_konsolidasi_2026-04.csv  ← Output (generated)
└── log_2026-04.txt           ← Log file (generated)
```

---

## ✅ Key Features

| Aspek | Detail |
|-------|--------|
| **Input** | Website URLs (Claude discovers sendiri laporan yang sesuai period) |
| **Processing** | Sequential (1 company per Claude Code session) |
| **Output** | 1 centralized CSV per period (YYYY-MM) |
| **Language** | Bahasa Indonesia (all outputs, JSON keys, CSV headers, logs) |
| **Error Handling** | Log success/fail per company, skip errors, continue next |
| **Scalability** | 125 companies × multiple periods = easy to batch |
| **Flexibility** | Flag-based (YYYY, MM) = reusable untuk any period |

---

## 🚀 Execution Examples

```bash
# April 2026
./akuisisi_data.sh --2026 --04

# December 2025
./akuisisi_data.sh --2025 --12

# Loop semua bulan tahun 2026
for bulan in {01..12}; do
    ./akuisisi_data.sh --2026 --$(printf "%02d" $bulan)
done
```

---

## ⚠️ Dependencies

- `bash` (standard)
- `jq` (optional, untuk advanced parsing)
- `claude` command (Claude Code CLI, OAuth-based)
- Internet connection (untuk download PDFs)

---
