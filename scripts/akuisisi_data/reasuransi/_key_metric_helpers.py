"""Shared helpers for key metric extraction scripts."""
import csv
from pathlib import Path
from typing import List, Dict


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
