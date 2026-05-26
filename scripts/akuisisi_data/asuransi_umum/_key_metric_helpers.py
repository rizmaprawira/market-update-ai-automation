"""Shared helpers for key metric extraction scripts."""
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


# Standard OJK label patterns for asuransi_umum — fallback when company-specific keywords fail
STANDARD_UMUM_FALLBACKS = {
    "aset":                    [r"Total Aset\b"],
    "ekuitas":                 [r"V\. Ekuitas", r"IV\. Ekuitas"],
    "pendapatan_premi":        [r"Pendapatan Premi\b"],
    "premi_bruto":             [r"Premi Bruto\b"],
    "premi_reasuransi":        [r"Premi Reasuransi\b"],
    "premi_neto":              [r"Premi Neto\b", r"Premi Netto\b", r"Premi-Neto\b"],
    "hasil_underwriting":      [r"Hasil Underwriting\b", r"Hasil Underwriting Bersih\b"],
    "laba_rugi_komprehensif":  [r"Total Laba.*Komprehensif", r"\bLaba Komprehensif\b"],
    "rasio_solvabilitas":      [r"Rasio Pencapaian \(%\)", r"Rasio Pencapaian \(dalam %\)"],
    "rasio_likuiditas":        [],
}


def get_period_dir(output_root: str = "data", yyyy: int = 2026, mm: int = 1) -> Path:
    """Get period directory, respecting custom output_root."""
    return Path(output_root) / f"{yyyy}-{mm:02d}"


def extract_two_numbers_semantic(
    text: str,
    keywords: List[str],
    field_name: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract two numbers from text based on keyword patterns (semantic search).

    More robust than line-number dependent approach. Finds keyword anywhere in text,
    then extracts the two closest meaningful numbers after it.

    Args:
        text: Full text to search
        keywords: List of keyword patterns to try (in priority order)
        field_name: Optional field name for auto-applying standard OJK fallbacks

    Returns:
        Tuple of (current_period_value, previous_period_value) or (None, None)
    """
    text = re.sub(r"\s+", " ", text)

    def extract_numbers_after_keyword(keyword_pattern: str):
        """Find keyword pattern and extract two large numbers after it."""
        try:
            pattern = re.compile(keyword_pattern, re.IGNORECASE)
            match = pattern.search(text)
            if not match:
                return None, None

            # Get text after the keyword, search in next 300 chars
            start_pos = match.end()
            context_text = text[start_pos:start_pos + 300]

            # Extract numbers with their positions
            number_pattern = r"([0-9]+(?:[.,][0-9]+)*)"
            numbers_with_pos = [(m.group(1), m.start()) for m in re.finditer(number_pattern, context_text)]

            if len(numbers_with_pos) < 2:
                return None, None

            # Filter for larger numbers (likely to be the actual values, not line numbers)
            # Line numbers are typically 1-50, so look for larger numbers
            large_numbers = [n for n in numbers_with_pos if len(n[0].replace(".", "").replace(",", "")) > 3]

            if len(large_numbers) < 2:
                # Fallback: just take first two non-trivial numbers
                large_numbers = numbers_with_pos

            if len(large_numbers) >= 2:
                return large_numbers[0][0], large_numbers[1][0]

            return None, None
        except Exception:
            return None, None

    # Try each company-specific keyword pattern in order
    for keyword in keywords:
        val1, val2 = extract_numbers_after_keyword(keyword)
        if val1 is not None and val2 is not None:
            return val1, val2

    # If still no match and field_name is provided, try standard OJK fallback patterns
    if field_name and field_name in STANDARD_UMUM_FALLBACKS:
        for keyword in STANDARD_UMUM_FALLBACKS[field_name]:
            val1, val2 = extract_numbers_after_keyword(keyword)
            if val1 is not None and val2 is not None:
                return val1, val2

    return None, None


def upsert_database_csv(
    database_csv_path: Path,
    new_rows: List[Dict],
    columns: List[str],
) -> None:
    """
    Upsert rows to database CSV.

    If a row with the same (periode, nama_perusahaan) exists, replace it.
    Otherwise, append as new row.

    Args:
        database_csv_path: Path to database CSV file
        new_rows: List of dicts to upsert
        columns: List of column names in CSV order
    """
    existing_rows = []

    if database_csv_path.exists():
        with database_csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="|")
            existing_rows = list(reader) if reader else []

    # Create set of (periode, nama_perusahaan) tuples from new rows for fast lookup
    new_keys = {(row["periode"], row["nama_perusahaan"]) for row in new_rows}

    # Keep existing rows that are NOT being replaced
    filtered_existing = [
        row for row in existing_rows
        if (row.get("periode"), row.get("nama_perusahaan")) not in new_keys
    ]

    # Combine: filtered existing + new rows
    final_rows = filtered_existing + new_rows

    # Write back
    with database_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="|")
        writer.writeheader()
        writer.writerows(final_rows)
