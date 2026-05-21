# Lesson Learned: Reasuransi Metrics Extraction Script

## Context
Developed `pt_maskapai_reasuransi_indonesia_extract.py` to extract 9 key financial metrics from pdftotext output and aggregate into period-level database.

---

## What Went Well ✅

### 1. Dynamic Path Resolution
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
period_dir = PROJECT_ROOT / "data" / f"{args.yyyy}-{args.mm:02d}"
```
- Script works from anywhere, no hardcoded paths
- Auto-discovers project structure based on file location
- **Lesson:** Use relative path resolution, not absolute

### 2. Two-Stage Output Architecture
```
Input TXT → Extract → Company CSV + Period Database CSV
```
- Per-company CSV: retains full data locally for reference
- Period database CSV: centralized aggregation for all companies
- Clear separation of concerns
- **Lesson:** Keep detailed output + summary output, don't force single source of truth

### 3. Append Mode for Aggregation
```python
file_exists = DATABASE_CSV.exists()
mode = "a" if file_exists else "w"
```
- Multiple companies write to same period database without overwriting
- Enables batch processing or sequential runs
- **Lesson:** Append pattern prevents data loss when coordinating multi-step pipelines

### 4. Generic Extraction Function
```python
def extract_two_numbers(text: str, keyword: str):
    # Reusable for all metrics: aset, ekuitas, premi, rasio, etc.
```
- Single function handles all 9 metrics with keyword parameter
- Reduces duplication, easier to fix extraction bugs
- **Lesson:** Parameterize what varies, consolidate what's common

---

## What Was Fragile ⚠️

### 1. Hard-Coded Company Metadata
```python
company = "PT Maskapai Reasuransi Indonesia Tbk."
jenis = "Reasuransi"
```
- Company name, insurance type baked into script
- Must modify 2 lines per new company
- Risk: inconsistency if names not updated correctly
- **Risk:** Can't scale to 7 companies without duplication

### 2. Keywords Are Brittle
```python
aset_2026, aset_prev = extract_two_numbers(text, "34 Jumlah Aset (20 + 33)")
```
- Exact text match required
- Each company's laporan keuangan may have different line numbers/labels
  - "34 Jumlah Aset" vs "X Jumlah Aset" for Orion
  - Different Indonesian phrasing across companies
- **Risk:** Keywords must be verified per company; silent failures (None values) if text doesn't match
- **Lesson:** Never assume format consistency across companies

### 3. Hard-Coded Extraction Calls
```python
aset_2026, aset_prev = extract_two_numbers(text, "...")
ekuitas_2026, ekuitas_prev = extract_two_numbers(text, "...")
# ... repeated 9 times
```
- 8 separate extraction lines; hard to maintain
- If a company has different metrics or ordering, need refactor
- **Lesson:** Map should be data-driven, not imperative calls

### 4. No Validation or Debugging
```python
if not m:
    return None, None  # Silent failure
```
- When keyword doesn't match, returns None without warning
- Hard to debug which metrics failed extraction
- **Lesson:** Log warnings when extraction fails, especially for new companies

---

## Pattern for Scaling to 7 Companies

### Current State (Single Company)
```python
# pt_maskapai_reasuransi_indonesia_extract.py
company = "PT Maskapai Reasuransi Indonesia Tbk."
keywords = {
    'aset': '34 Jumlah Aset (20 + 33)',
    'ekuitas': '20 Jumlah Ekuitas (16 s/d 19)',
    # ... hard-coded
}
```

### Phase 1: Identify Keyword Differences (Before Refactor)
- Test 2-3 companies (Orion, Reasuransi Indonesia Utama)
- Document which keywords differ
- Validate that metrics are indeed the same across companies

### Phase 2: Refactor to Template Class
```python
class ResuransiExtractor:
    def __init__(self, company_slug, company_name, yyyy, mm):
        self.company_slug = company_slug
        self.company_name = company_name
        self.yyyy = yyyy
        self.mm = mm
    
    def get_keywords(self):
        """Override per company"""
        raise NotImplementedError
    
    def extract(self):
        """Common extraction logic"""
        text = self._read_input()
        rows = self._extract_metrics(text)
        self._write_outputs(rows)
    
    def _extract_metrics(self, text):
        """Extract all metrics using keyword map"""
        keywords = self.get_keywords()
        rows = []
        for metric, keyword in keywords.items():
            current, prev = extract_two_numbers(text, keyword)
            rows.append({metric: current, f"{metric}_prev": prev})
        return rows


class MareInExtractor(ResuransiExtractor):
    def get_keywords(self):
        return {
            'aset': '34 Jumlah Aset (20 + 33)',
            'ekuitas': '20 Jumlah Ekuitas (16 s/d 19)',
            # ...
        }


class OrionExtractor(ResuransiExtractor):
    def get_keywords(self):
        return {
            'aset': 'X Jumlah Aset...',  # Orion-specific
            'ekuitas': 'Y Jumlah Ekuitas...',
            # ...
        }
```

### Phase 3: CLI Wrapper for Batch Processing
```python
if __name__ == "__main__":
    parser.add_argument('--company', choices=[
        'pt_maskapai_reasuransi_indonesia',
        'pt_orion_reasuransi_indonesia',
        'pt_reasuransi_indonesia_utama',
        # ... all 7
    ])
    parser.add_argument('--yyyy', type=int)
    parser.add_argument('--mm', type=int)
    parser.add_argument('--all', action='store_true', help='Process all companies')
    
    extractors = {
        'pt_maskapai_reasuransi_indonesia': MareInExtractor,
        'pt_orion_reasuransi_indonesia': OrionExtractor,
        # ...
    }
    
    if args.all:
        for company, ExtractorClass in extractors.items():
            extractor = ExtractorClass(...)
            extractor.extract()
    else:
        ExtractorClass = extractors[args.company]
        extractor = ExtractorClass(...)
        extractor.extract()
```

**Usage:**
```bash
# Single company
python extract_reasuransi.py --company pt_orion_reasuransi_indonesia --yyyy 2026 --mm 04

# All companies for a period
python extract_reasuransi.py --all --yyyy 2026 --mm 04
```

---

## Key Principles for Next Iteration

1. **DRY:** No code duplication across companies
   - Common logic in base class
   - Company-specific data in config (keywords, name)

2. **Testability:** Test base extraction logic once
   - Test keyword overrides per company
   - Validates per company separately

3. **Maintainability:** Bug fix applies to all companies
   - Fix in base class, no need to touch subclasses

4. **Debuggability:** Log extraction failures
   - Warn when keyword not found
   - Easy to identify which metrics failed for which company

5. **Scalability:** Adding company 8+ is just 1 subclass
   - No changes to base logic
   - No changes to main script

---

## Decision Point

**When to refactor:** After validating 2-3 additional companies confirm:
- ✅ Same 9 metrics needed for all
- ✅ Keywords vary but pattern is identifiable
- ✅ Output format (two-stage) works well

**Not worth refactoring if:** Each company needs completely custom logic → build company-specific scripts instead

---

## File Structure After Refactor
```
scripts/extract/
├── extract_reasuransi.py              # Main entry point (refactored, generic)
├── extractors/
│   ├── __init__.py
│   ├── base.py                        # ResuransiExtractor base class
│   ├── pt_maskapai_reasuransi.py      # MareInExtractor subclass
│   ├── pt_orion_reasuransi.py         # OrionExtractor subclass
│   └── ...
├── LESSONLEARNED.md                   # This file
└── README.md                           # Usage guide
```
