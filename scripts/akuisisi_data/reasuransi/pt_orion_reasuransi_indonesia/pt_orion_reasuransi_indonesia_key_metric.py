#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _key_metric_helpers import upsert_database_csv, extract_two_numbers_semantic, get_period_dir

COLUMNS = [
    "periode",
    "jenis_asuransi",
    "nama_perusahaan",
    "aset",
    "ekuitas",
    "premi_penutupan_tidak_langsung",
    "premi_bruto",
    "pendapatan_premi",
    "hasil_underwriting",
    "laba_rugi_komprehensif",
    "rasio_solvabilitas",
    "rasio_likuiditas",
]


def extract_two_numbers(text: str, keywords):
    """
    Extract two numbers using semantic/content-based search.
    Keywords can be a string (for backward compatibility) or list of patterns.
    """
    if isinstance(keywords, str):
        keywords = [keywords]
    return extract_two_numbers_semantic(text, keywords)


def main():
    parser = argparse.ArgumentParser(description="Extract Orion metrics from TXT file")
    parser.add_argument("--yyyy", type=int, default=2026, help="Year (default: 2026)")
    parser.add_argument("--mm", type=int, default=3, help="Month (default: 3)")
    parser.add_argument("--output-root", type=str, default="data", help="Output root directory (default: data)")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    period_dir = get_period_dir(args.output_root, args.yyyy, args.mm)
    company_dir = period_dir / "reasuransi" / "pt_orion_reasuransi_indonesia"
    INPUT_TXT = company_dir / f"pt_orion_reasuransi_indonesia_{args.yyyy}_{args.mm:02d}.txt"
    COMPANY_CSV = company_dir / f"pt_orion_reasuransi_indonesia_key_metric_{args.yyyy}_{args.mm:02d}.csv"
    DATABASE_CSV = period_dir / f"database_reasuransi_{args.yyyy}_{args.mm:02d}.csv"

    text = INPUT_TXT.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)

    company = "PT Orion Reasuransi Indonesia"
    jenis = "Reasuransi"

    aset_2026, aset_prev = extract_two_numbers(text, [
        r"Jumlah Aset\s*\(\d+\s*\+\s*\d+\)",
        r"Total Assets",
        r"JUMLAH ASET"
    ])
    ekuitas_2026, ekuitas_prev = extract_two_numbers(text, [
        r"Jumlah Ekuitas",
        r"Total Equity",
        r"TOTAL EKUITAS"
    ])
    premi_tl_2026, premi_tl_2025 = extract_two_numbers(text, [
        r"Premi Penutupan Tidak Langsung",
        r"Indirect Premiums",
        r"Premi.*Tidak.*Langsung"
    ])
    premi_bruto_2026, premi_bruto_2025 = extract_two_numbers(text, [
        r"Jumlah Premi Bruto",
        r"Total Gross Premiums",
        r"Premi.*Bruto"
    ])
    pend_premi_2026, pend_premi_2025 = extract_two_numbers(text, [
        r"Jumlah Pendapatan Premi",
        r"Total Premiums Income",
        r"Pendapatan.*Premi"
    ])
    hasil_uw_2026, hasil_uw_2025 = extract_two_numbers(text, [
        r"HASIL UNDERWRITING",
        r"UNDERWRITING INCOME",
        r"Hasil.*Underwriting"
    ])
    laba_komp_2026, laba_komp_2025 = extract_two_numbers(text, [
        r"TOTAL LABA.*KOMPREHENSIF",
        r"TOTAL COMPREHENSIVE INCOME",
        r"Laba.*Komprehensif"
    ])
    solv_2026, solv_prev = extract_two_numbers(text, [
        r"Rasio Pencapaian Solvabilitas",
        r"Solvency Margin Ratio",
        r"Solvabilitas"
    ])
    lik_2026, lik_prev = extract_two_numbers(text, [
        r"Rasio Likuiditas",
        r"Liquidity Ratio",
        r"Likuiditas\s*\(%\)"
    ])

    current_period = f"{args.yyyy}-{args.mm:02d}"
    prev_year = args.yyyy - 1
    prev_period = f"{prev_year}-{args.mm:02d}"
    rows = [
        {
            "periode": current_period,
            "jenis_asuransi": jenis,
            "nama_perusahaan": company,
            "aset": aset_2026,
            "ekuitas": ekuitas_2026,
            "premi_penutupan_tidak_langsung": premi_tl_2026,
            "premi_bruto": premi_bruto_2026,
            "pendapatan_premi": pend_premi_2026,
            "hasil_underwriting": hasil_uw_2026,
            "laba_rugi_komprehensif": laba_komp_2026,
            "rasio_solvabilitas": solv_2026,
            "rasio_likuiditas": lik_2026,
        },
        {
            "periode": prev_period,
            "jenis_asuransi": jenis,
            "nama_perusahaan": company,
            "aset": aset_prev,
            "ekuitas": ekuitas_prev,
            "premi_penutupan_tidak_langsung": premi_tl_2025,
            "premi_bruto": premi_bruto_2025,
            "pendapatan_premi": pend_premi_2025,
            "hasil_underwriting": hasil_uw_2025,
            "laba_rugi_komprehensif": laba_komp_2025,
            "rasio_solvabilitas": solv_prev,
            "rasio_likuiditas": lik_prev,
        },
    ]

    with COMPANY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="|")
        writer.writeheader()
        writer.writerows(rows)

    upsert_database_csv(DATABASE_CSV, rows, COLUMNS)

    print(f"Wrote {COMPANY_CSV}")
    print(f"Upserted {DATABASE_CSV}")


if __name__ == "__main__":
    main()
