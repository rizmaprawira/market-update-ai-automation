#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path

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


def extract_two_numbers(text: str, keyword: str):
    pattern = re.compile(
        rf"{re.escape(keyword)}\s+(\(?[0-9\.,-]+\)?)\s+(\(?[0-9\.,-]+\)?)",
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
    parser = argparse.ArgumentParser(description="Extract MAREIN metrics from TXT file")
    parser.add_argument("--yyyy", type=int, default=2026, help="Year (default: 2026)")
    parser.add_argument("--mm", type=int, default=3, help="Month (default: 3)")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    period_dir = PROJECT_ROOT / "data" / f"{args.yyyy}-{args.mm:02d}"
    company_dir = period_dir / "pt_maskapai_reasuransi_indonesia"
    INPUT_TXT = company_dir / f"pt_maskapai_reasuransi_indonesia_{args.yyyy}_{args.mm:02d}.txt"
    COMPANY_CSV = company_dir / f"pt_maskapai_reasuransi_indonesia_key_metric_{args.yyyy}_{args.mm:02d}.csv"
    DATABASE_CSV = period_dir / f"database_reasuransi_{args.yyyy}_{args.mm:02d}.csv"

    text = INPUT_TXT.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)

    company = "PT Maskapai Reasuransi Indonesia Tbk."
    jenis = "Reasuransi"

    aset_2026, aset_prev = extract_two_numbers(text, "34 Jumlah Aset (20 + 33)")
    ekuitas_2026, ekuitas_prev = extract_two_numbers(text, "20 Jumlah Ekuitas (16 s/d 19)")
    premi_tl_2026, premi_tl_2025 = extract_two_numbers(text, "b. Premi Penutupan Tidak Langsung")
    premi_bruto_2026, premi_bruto_2025 = extract_two_numbers(text, "4 Jumlah Premi Bruto")
    pend_premi_2026, pend_premi_2025 = extract_two_numbers(text, "2 Jumlah Pendapatan Premi")
    hasil_uw_2026, hasil_uw_2025 = extract_two_numbers(text, "17 HASIL UNDERWRITING")
    laba_komp_2026, laba_komp_2025 = extract_two_numbers(text, "27 TOTAL LABA (RUGI) KOMPREHENSIF")
    solv_2026, solv_prev = extract_two_numbers(text, "D. Rasio Pencapaian Solvabilitas (%) *)")
    lik_2026, lik_prev = extract_two_numbers(text, "b. Rasio Likuiditas (%)")

    # Catatan: tabel posisi keuangan & kesehatan membandingkan current vs prev year,
    # sedangkan tabel laba rugi membandingkan current vs same month prev year.
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

    db_exists = DATABASE_CSV.exists()
    db_mode = "a" if db_exists else "w"
    with DATABASE_CSV.open(db_mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="|")
        if not db_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {COMPANY_CSV}")
    print(f"Appended to {DATABASE_CSV}" if db_exists else f"Created {DATABASE_CSV}")


if __name__ == "__main__":
    main()
