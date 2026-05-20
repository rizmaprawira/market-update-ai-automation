# Troubleshooting Guide

> Legacy note: file ini berfokus pada alur v2 berbasis Claude. Untuk alur default Codex v3, gunakan `docs/TROUBLESHOOTING_CODEX_V3.md`.

## Common Issues & Solutions

### Claude CLI Issues

#### "Claude is not installed" or "command not found: claude"

```bash
# Check if Claude CLI is installed
which claude

# If not installed, install from https://claude.ai/code
# Then authenticate
claude login
```

#### "Claude cannot run non-interactively"

```bash
# Test if Claude accepts piped input
echo "Hitung 2+2" | claude --print

# If this fails, the --print flag may not be supported
# Try without --print:
echo "Hitung 2+2" | claude
```

#### "Permissions denied" during script execution

The script needs pre-approved tool permissions. Verify `.claude/settings.json` exists:

```bash
cat .claude/settings.json
```

Should contain:
```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "WebFetch"]
  }
}
```

If it's missing or incomplete:
```bash
mkdir -p .claude
cat > .claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "WebFetch"]
  }
}
EOF
```

---

### Script Execution Issues

#### "File not found: config/companies.txt"

```bash
# Check if file exists
ls -la config/companies.txt

# If missing, use test file instead
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --companies config/test_companies.txt
```

#### "Invalid month" or "Invalid year" errors

```bash
# Month must be 2 digits (01-12), year 4 digits
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04   # ✓ correct
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 4    # ✗ wrong: MM=4, should be 04
bash scripts/akuisisi_data_v2.sh --YYYY 26 --MM 04     # ✗ wrong: YYYY=26, should be 2026
```

#### "Delay must be a number"

```bash
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --delay 5   # ✓ correct
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --delay abc # ✗ wrong
```

---

### Data Extraction Issues

#### "PDF download failed" or "Cannot read PDF"

**Symptom:** `status.txt` shows `GAGAL`, no PDF file in company directory.

**Solutions:**
1. Install `pdftotext` for reliable PDF extraction:
   ```bash
   # macOS
   brew install poppler
   
   # Linux (Ubuntu/Debian)
   sudo apt-get install poppler-utils
   
   # Verify installation
   which pdftotext
   ```

2. Some websites block non-browser requests. The script may need a User-Agent header.

3. Check website accessibility manually:
   ```bash
   curl -L "https://inare.co.id/en/report/" | head -20
   ```

#### "JSON file is empty or malformed"

**Symptom:** `data_ekstrak.json` exists but contains no data.

**Possible causes:**
- PDF could not be read (retry with pdftotext installed)
- JSON structure does not match prompt template
- Claude encountered a parsing error

**Debug:**
```bash
# Check the extraction notes in JSON
cat data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_raw.json | jq '.extraction_notes'

# Look for parsing_issues or missing_fields
```

#### "CSV has wrong number of columns"

**Symptom:** `wc -L` shows CSV rows with != 12 columns.

**Possible causes:**
- A value in the CSV contains a pipe character (`|`), breaking the delimiter
- Whitespace or newlines in extracted values
- Data includes currency symbols or text units

**Debug:**
```bash
# Check the problematic CSV row
cat data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_row.csv | awk -F'|' '{print NF}'

# If NF != 12, examine the raw values
cat data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_raw.json | jq '.balance_sheet'
```

**Fix:**
The prompt template explicitly removes units and escapes special characters. Ensure the prompt is being applied correctly.

---

### Output & Consolidation Issues

#### "Consolidated CSV is empty or has only header"

**Symptom:** `wc -l data/2026-04/database_konsolidasi.csv` shows only 1 line.

**Possible causes:**
- No companies were processed successfully
- CSV validation failed for all companies

**Debug:**
```bash
# Check the log for errors
tail -100 data/2026-04/log.txt

# Check status.txt for each company
grep -r "." data/2026-04/*/status.txt | head -20

# Check for validation errors in log
grep "VALIDATION FAILED" data/2026-04/log.txt
```

#### "CSV rows have N/A values"

**Symptom:** Some fields in CSV show `N/A` instead of numbers.

**Expected behavior:** This is normal if:
- Field was not found in the PDF
- Data extraction partially failed (status should be `PARSIAL`)

**To debug:**
```bash
# Check extraction notes
cat data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_raw.json | jq '.extraction_notes.missing_fields'

# Check status
cat data/2026-04/pt_tugu_reasuransi_indonesia/status.txt

# If status is BERHASIL but CSV has N/A, something is wrong
# This would indicate an inconsistency between JSON and status.txt
```

#### "Resume doesn't work"

**Symptom:** Running with `--resume` flag doesn't skip completed companies.

**Debug:**
```bash
# Check checkpoint file
cat data/2026-04/.checkpoint_2026-04.txt

# Should contain lines like:
# SUCCESS:https://inare.co.id/en/report/
# SUCCESS:https://www.indonesiare.co.id/...
# FAILED:https://some_failing_url

# If file is empty or malformed, resume won't work
```

**Solution:**
- Manually edit `.checkpoint_2026-04.txt` to list URLs that succeeded
- Or delete the checkpoint and re-run without `--resume`

---

### Validation Errors

#### "Validation failed: CSV file not found"

**Symptom:** Log shows validation errors but CSV file exists.

**Possible causes:**
- CSV file is empty (no rows)
- CSV path is wrong in script

**Debug:**
```bash
ls -la data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_row.csv
wc -l data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_row.csv
```

#### "Validation failed: wrong number of columns"

**Symptom:** Script shows validation error for column count.

**Debug:**
```bash
# Check actual column count
awk -F'|' '{print NF}' data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_row.csv

# Count manually
cat data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_row.csv | tr '|' '\n' | wc -l
```

#### "Validation failed: period field is wrong"

**Symptom:** Script rejects CSV because first field doesn't match `YYYY-MM`.

**Debug:**
```bash
# Extract first field
cut -d'|' -f1 data/2026-04/pt_tugu_reasuransi_indonesia/tugu_re_row.csv
```

Should match the target period (e.g., `2026-04`).

---

### Analysis & Plotting Issues

#### "plot_metrics_reasuransi.py fails"

```bash
# Check if Python is installed
python3 --version

# Check if required packages are available
python3 -c "import matplotlib, pandas, numpy"

# If packages missing, install them
pip3 install matplotlib pandas numpy
```

#### "Plot script says 'No CSV file found'"

```bash
python3 analysis/plot_metrics_reasuransi.py \
  --input data/2026-04/database_konsolidasi.csv \
  --output-dir data/2026-04/plots
```

Make sure the `--input` path is correct and the CSV file exists.

---

### Network & Website Issues

#### "Website cannot be accessed" or "Connection timeout"

**Symptom:** Claude reports website is unreachable, status = `GAGAL`.

**Possible causes:**
1. Website is down or behind geo-blocking
2. Website blocks automated requests
3. Network connectivity issue

**Debug:**
```bash
# Test website accessibility
curl -L -I "https://inare.co.id/en/report/" 2>&1 | head -5

# Try with User-Agent header
curl -L -H "User-Agent: Mozilla/5.0" "https://inare.co.id/en/report/" | head -20
```

**Workaround:** 
The prompt can be modified to include a User-Agent header in the curl command inside Claude's prompt.

#### "Website structure has changed"

**Symptom:** Many companies suddenly show `TIDAK_DITEMUKAN` status.

**Possible causes:**
- Website redesigned, report link location changed
- Reporting format or schedule changed

**Debug:**
1. Manually check one company's website
2. Verify the report is actually published
3. Note any navigation changes needed
4. Update the prompt template to guide Claude to the new location

---

### Performance Issues

#### "Script takes too long"

**Possible causes:**
- Delay between companies is too high (`--delay 10`)
- Website is slow to respond
- PDF download is taking long time

**Solutions:**
```bash
# Reduce delay
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --delay 2

# Or set delay to 0 for testing (but may rate-limit)
bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --delay 0
```

#### "Memory usage is high"

Possible causes:
- JSON extraction for large PDF is storing entire PDF in memory
- Processing many companies simultaneously

**Solutions:**
- Run script with smaller batches
- Monitor with: `top` or `Activity Monitor` (macOS)

---

### File System Issues

#### "Permission denied" when writing output

**Symptom:** Script cannot create directories or write files.

**Debug:**
```bash
# Check data/ directory permissions
ls -la data/
chmod 755 data/

# Try creating a test file
touch data/test.txt
rm data/test.txt
```

#### "Disk space exhausted"

```bash
# Check available space
df -h

# Check size of data directory
du -sh data/

# Remove old periods if space is critical
rm -rf data/2025-01/  # Keep only recent months
```

---

## Getting Help

If you encounter an issue not listed here:

1. **Check the log:**
   ```bash
   tail -200 data/YYYY-MM/log.txt
   ```

2. **Look at extraction notes:**
   ```bash
   cat data/YYYY-MM/{company}/*/raw.json | jq '.extraction_notes'
   ```

3. **Try a single-company test:**
   ```bash
   bash scripts/akuisisi_data_v2.sh --YYYY 2026 --MM 04 --companies config/test_companies.txt
   ```

4. **Enable debug mode** (if available):
   - Some scripts have `set -x` for verbose output
   - Uncomment in the script if needed

5. **Check Claude's response:**
   - Look at the per-company directory for `{company}_raw.json`
   - Examine `extraction_notes` section for clues
