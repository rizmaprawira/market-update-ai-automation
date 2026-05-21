#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _key_metric_helpers import upsert_database_csv

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


def extract_two_numbers(text: str, keyword: str):
    pattern = re.compile(
        rf"{re.escape(keyword)}\s+(\(?[0-9\.,%\-]+\)?)\s+(\(?[0-9\.,%\-]+\)?)",
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if not m:
        return None, None

    def norm(s: str) -> str:
        s = s.strip()
        if s.startswith("(") and s.endswith(")"):
            return "-" + s[1:-1]
        return s

    return norm(m.group(1)), norm(m.group(2))


def main():
    parser = argparse.ArgumentParser(description="Extract Binagriya Upakara metrics from TXT file")
    parser.add_argument("--yyyy", type=int, default=2026, help="Year (default: 2026)")
    parser.add_argument("--mm", type=int, default=4, help="Month (default: 4)")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    period_dir = PROJECT_ROOT / "data" / f"{args.yyyy}-{args.mm:02d}"
    company_dir = period_dir / "asuransi_umum" / "pt_asuransi_binagriya_upakara"
    INPUT_TXT = company_dir / f"pt_asuransi_binagriya_upakara_{args.yyyy}_{args.mm:02d}.txt"
    COMPANY_CSV = company_dir / f"pt_asuransi_binagriya_upakara_key_metric_{args.yyyy}_{args.mm:02d}.csv"
    DATABASE_CSV = period_dir / f"database_asuransi_umum_{args.yyyy}_{args.mm:02d}.csv"

    text = INPUT_TXT.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)

    company = "PT Asuransi Binagriya Upakara"
    jenis = "Asuransi Umum"

    aset_2026, aset_prev = extract_two_numbers(text, "34 JUMLAH ASET (21+33)")
    ekuitas_2026, ekuitas_prev = extract_two_numbers(text, "21 JUMLAH EKUITAS (16 s/d 20)")
    pend_premi_2026, pend_premi_prev = extract_two_numbers(text, "5 Jumlah Pendapatan Premi (3+4)")
    premi_bruto_2026, premi_bruto_prev = extract_two_numbers(text, "7 Jumlah Premi Bruto (5-6)")
    premi_reasu_2026, premi_reasu_prev = extract_two_numbers(text, "11 Jumlah Premi Reasuransi (9-10)")
    premi_neto_2026, premi_neto_prev = extract_two_numbers(text, "12 Premi Neto (7-11)")
    hasil_uw_2026, hasil_uw_prev = extract_two_numbers(text, "29 HASIL UNDERWRITING (20-28)")
    laba_komp_2026, laba_komp_prev = extract_two_numbers(text, "47 LABA (RUGI) KOMPREHENSIF (45+46)")
    solv_2026, solv_prev = extract_two_numbers(text, "D. RASIO PENCAPAIAN SOLVABILITAS (% )*")
    lik_2026, lik_prev = extract_two_numbers(text, "b. Rasio Likuiditas (% )")

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
