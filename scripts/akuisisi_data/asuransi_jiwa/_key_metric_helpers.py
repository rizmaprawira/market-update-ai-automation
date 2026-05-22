"""Shared helpers for key metric extraction scripts."""
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


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


def extract_two_numbers(text: str, keyword: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract two consecutive numbers from text matching keyword.
    Works with both line-based and whitespace-collapsed text formats.
    Handles: thousands separators, decimals, negatives in parentheses.

    Returns:
        Tuple of (current_value, previous_value) or (None, None) if not found.
        Negative numbers in parentheses are converted to "-" prefix format.
    """
    # Pattern for numbers: 29,550,220 or 26475571 or 123.456,78 or (123) or -123
    number_pattern = r'-?\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d+)?|\(-?\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d+)?\)'

    # Try line-based search first (for structured documents)
    for line in text.split('\n'):
        if keyword.lower() not in line.lower():
            continue

        # Find numbers IMMEDIATELY AFTER the keyword (and any descriptive text)
        # Look for keyword, possibly followed by non-digit text, then numbers
        match = re.search(
            rf"{re.escape(keyword)}.*?({number_pattern})\s+({number_pattern})",
            line,
            re.IGNORECASE
        )
        if match:
            def normalize(s: str) -> str:
                s = s.strip()
                if s.startswith('(') and s.endswith(')'):
                    return '-' + s[1:-1]
                return s
            return normalize(match.group(1)), normalize(match.group(2))

    # Fallback: if collapsed text (all whitespace converted to spaces)
    # Look for keyword followed by numbers in the entire text
    match = re.search(
        rf"{re.escape(keyword)}.*?({number_pattern})\s+({number_pattern})",
        text,
        re.IGNORECASE
    )
    if match:
        def normalize(s: str) -> str:
            s = s.strip()
            if s.startswith('(') and s.endswith(')'):
                return '-' + s[1:-1]
            return s
        return normalize(match.group(1)), normalize(match.group(2))

    return None, None
