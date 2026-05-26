# Stress Test Auto-Fix Framework

## Common Error Patterns & Fixes

### 1. PDF Download Failures
**Symptoms:** No PDF file created, timeout errors in logs
**Root Causes:**
- Website layout changed (need to update CSS selectors)
- Dynamic JavaScript content not loading
- Network timeouts (too aggressive timeout value)
- Anti-bot detection (IP blocking, rate limiting)

**Fixes to Apply:**
```python
# In company download scripts:
- Increase timeout from 30s to 40-50s for slow sites
- Add wait for dynamic content: page.wait_for_load_state("networkidle")
- Add retry logic with exponential backoff
- Add user-agent rotation for anti-bot
- Update CSS selectors if website changed
```

### 2. PDF Text Extraction Failures
**Symptoms:** .txt file missing or empty, garbled text
**Root Causes:**
- PDF has no extractable text (image-based PDF)
- Encoding issues
- pdftotext doesn't handle special characters

**Fixes to Apply:**
```bash
# In pdftotext phase:
- Always use -layout flag: pdftotext -layout input.pdf output.txt
- Add fallback to OCR if text extraction fails
- Validate text file size > 100 bytes
- Check for "error" strings in text output
```

### 3. Metrics Extraction NaN Values
**Symptoms:** CSV has N/A values, status=PARSIAL
**Root Causes:**
- Pattern matching regex doesn't find metric
- Metric name in PDF differs from expected keyword
- Number format issues (comma vs period, currency symbols)

**Fixes to Apply:**
```python
# In company metrics extractors:
- Add case-insensitive matching
- Check for alternative metric names/spellings
- Strip currency symbols and separators
- Add extraction notes logging
- Validate number conversions
```

### 4. CSV Validation Failures
**Symptoms:** CSV format error, wrong column count
**Root Causes:**
- Pipe delimiter not consistent
- Too few/many columns extracted
- Data type conversion errors

**Fixes to Apply:**
```python
# In metrics extraction:
- Validate exactly 12 columns, pipe-delimited
- Convert numbers properly: str(int(val.replace(",", "")))
- Handle N/A gracefully
- Log CSV before write for debugging
```

## Priority Order for Fixes

1. **Network/Timeout Issues** (highest impact)
   - Increase timeout threshold
   - Add retry logic
   - Check website availability

2. **Selector/Layout Changes** (high impact)
   - Update CSS selectors for changed websites
   - Update wait conditions

3. **Pattern Matching** (medium impact)
   - Add alternative keyword matching
   - Improve number format handling

4. **Data Validation** (lower impact)
   - Better error messages
   - Improve data type conversions

## Test & Verify Workflow

For each fix:
1. Identify affected companies (grep logs for specific error)
2. Modify relevant script (download or metrics extractor)
3. Test on 1-2 companies first (manual run)
4. Run full test with --resume to reprocess failed companies
5. Verify error rate < 5%

## Quick Commands

```bash
# Find companies with specific error
grep -r "GAGAL" data/2024-09/metrics/*/pt_*/*_status.txt

# Retest one company
cd scripts/akuisisi_data/{category}/{company_dir}/
python3 {company}_download.py --year 2024 --month 09

# Check extraction logs
cat data/2024-09/metrics/{category}/{company}/*_raw.json | jq '.extraction_notes'

# View failed company's error
tail -50 data/2024-09/log.txt | grep {company}
```
