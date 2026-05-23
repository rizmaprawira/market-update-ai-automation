#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _key_metric_helpers import upsert_database_csv, extract_two_numbers_semantic

COLUMNS = [
    "periode",
    "jenis_asuransi",
    "nama_perusahaan",
    "aset",
    "ekuitas",
    "pendapatan_premi",
    "premi_bruto",
    "premi_reasuransi",
    "premi_neto",
    "hasil_underwriting",
    "laba_rugi_komprehensif",
    "rasio_solvabilitas",
    "rasio_likuiditas",
]


def extract_two_numbers(text: str, keywords):
    if isinstance(keywords, str):
        keywords = [keywords]
    return extract_two_numbers_semantic(text, keywords)

def main():
    parser = argparse.ArgumentParser(description="Extract OONA metrics from TXT file")
    parser.add_argument("--yyyy", type=int, default=2026, help="Year (default: 2026)")
    parser.add_argument("--mm", type=int, default=4, help="Month (default: 4)")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    period_dir = PROJECT_ROOT / "data" / f"{args.yyyy}-{args.mm:02d}"
    company_dir = period_dir / "asuransi_umum" / "pt_asuransi_bina_dana_arta_tbk_oona_ins"
    INPUT_TXT = company_dir / f"pt_asuransi_bina_dana_arta_tbk_oona_ins_{args.yyyy}_{args.mm:02d}.txt"
    COMPANY_CSV = company_dir / f"pt_asuransi_bina_dana_arta_tbk_oona_ins_key_metric_{args.yyyy}_{args.mm:02d}.csv"
    DATABASE_CSV = period_dir / f"database_asuransi_umum_{args.yyyy}_{args.mm:02d}.csv"

    text = INPUT_TXT.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)

    company = "PT Asuransi Bina Dana Arta Tbk"
    jenis = "Asuransi Umum"

    aset_2026, aset_prev = extract_two_numbers(text, [r"Jumlah Aset", r"Total Assets", r"JUMLAH ASET"])
    ekuitas_2026, ekuitas_prev = extract_two_numbers(text, [r"Jumlah Ekuitas", r"Total Equity", r"TOTAL EKUITAS"])
    pend_premi_2026, pend_premi_prev = extract_two_numbers(text, [r"Jumlah Pendapatan Premi", r"Total Premiums Income"])
    premi_bruto_2026, premi_bruto_prev = extract_two_numbers(text, [r"Jumlah Premi Bruto", r"Total Gross Premiums"])
    premi_reasu_2026, premi_reasu_prev = extract_two_numbers(text, [r"Jumlah Premi Reasuransi"])
    premi_neto_2026, premi_neto_prev = extract_two_numbers(text, [r"Jumlah Premi Neto", r"Total Net Premiums"])
    hasil_uw_2026, hasil_uw_prev = extract_two_numbers(text, [r"HASIL UNDERWRITING", r"UNDERWRITING INCOME"])
    laba_komp_2026, laba_komp_prev = extract_two_numbers(text, [r"TOTAL LABA.*KOMPREHENSIF", r"TOTAL COMPREHENSIVE INCOME"])
    solv_2026, solv_prev = extract_two_numbers(text, [r"Rasio Pencapaian Solvabilitas", r"Solvency Margin Ratio"])
    lik_2026, lik_prev = extract_two_numbers(text, [r"Rasio Likuiditas", r"Liquidity Ratio"])

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
            "pendapatan_premi": pend_premi_2026,
            "premi_bruto": premi_bruto_2026,
            "premi_reasuransi": premi_reasu_2026,
            "premi_neto": premi_neto_2026,
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
            "pendapatan_premi": pend_premi_prev,
            "premi_bruto": premi_bruto_prev,
            "premi_reasuransi": premi_reasu_prev,
            "premi_neto": premi_neto_prev,
            "hasil_underwriting": hasil_uw_prev,
            "laba_rugi_komprehensif": laba_komp_prev,
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
