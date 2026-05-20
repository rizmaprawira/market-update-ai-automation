# Skill: Extract PDF Data

## Purpose

Extract complete financial data from a PDF report into structured JSON format.

## Inputs

- **pdf_file:** Path to downloaded PDF (laporan_keuangan.pdf)
- **output_dir:** Directory to save extracted JSON

## Outputs

- **{prefix}_raw.json:** Complete extracted financial data in structured format

## Format

The extracted JSON must include:

```json
{
  "extraction_metadata": { ... },
  "company_info": { ... },
  "balance_sheet": { ... },
  "income_statement": { ... },
  "financial_ratios": { ... },
  "governance": { ... },
  "notes_and_observations": [ ... ],
  "extraction_notes": {
    "sections_found": [ ... ],
    "sections_not_found": [ ... ],
    "parsing_issues": [ ... ],
    "missing_fields": { ... }
  }
}
```

## Key Requirements

- Extract **all** financial data from the PDF, not just key metrics
- Document which sections were found/not found in extraction_notes
- List any fields that will be N/A in the next step
- Save file even if extraction is partial

## See Also

- `docs/PROMPT_TEMPLATES.md` — Full prompt template
- `skills/skill_transform_json_to_csv/` — Next step (transform to CSV)
