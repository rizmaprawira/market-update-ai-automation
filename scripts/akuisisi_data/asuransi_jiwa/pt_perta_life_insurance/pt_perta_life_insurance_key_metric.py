#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _key_metric_helpers import upsert_database_csv, extract_two_numbers

COLUMNS = [
    "periode",
    "jenis_asuransi",
    "nama_perusahaan",
    "aset",
    "ekuitas",
    "pendapatan_premi",
    "premi_reasuransi",
    "premi_neto",
    "jumlah_pendapatan",
    "beban_komisi_tahun_pertama",
    "beban_komisi_tahun_lanjutan",
    "beban_komisi_overiding",
    "jumlah_beban_asuransi",
    "laba_rugi_komprehensif",
    "rasio_solvabilitas",
    "rasio_likuiditas",
]



def main():
    parser = argparse.ArgumentParser(description="Extract Perta Life metrics from TXT file")
    parser.add_argument("--yyyy", type=int, default=2026, help="Year (default: 2026)")
    parser.add_argument("--mm", type=int, default=3, help="Month (default: 3)")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    period_dir = PROJECT_ROOT / "data" / f"{args.yyyy}-{args.mm:02d}"
    company_dir = period_dir / "asuransi_jiwa" / "pt_perta_life_insurance"
    INPUT_TXT = company_dir / f"pt_perta_life_insurance_{args.yyyy}_{args.mm:02d}.txt"
    COMPANY_CSV = company_dir / f"pt_perta_life_insurance_key_metric_{args.yyyy}_{args.mm:02d}.csv"
    DATABASE_CSV = period_dir / f"database_asuransi_jiwa_{args.yyyy}_{args.mm:02d}.csv"

    if not INPUT_TXT.exists():
        print(f"Error: {INPUT_TXT} not found", file=sys.stderr)
        return 1

    text = INPUT_TXT.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)

    company = "PT Perta Life Insurance"
    jenis = "Asuransi Jiwa"

    # Note: Perta file has columns reversed (2025 first, 2026 second)
    aset_prev, aset_curr = extract_two_numbers(text, "Jumlah Aset (21 s.d. 34)")
    ekuitas_prev, ekuitas_curr = extract_two_numbers(text, "Jumlah Ekuitas (16 s.d. 19)")
    pend_premi_prev, pend_premi_curr = extract_two_numbers(text, "Pendapatan Premi")
    premi_reasu_prev, premi_reasu_curr = extract_two_numbers(text, "Premi Reasuransi")
    premi_neto_prev, premi_neto_curr = extract_two_numbers(text, "Jumlah Pendapatan Premi Neto")
    jml_pend_prev, jml_pend_curr = extract_two_numbers(text, "Jumlah Pendapatan")
    beban_komisi_tp_prev, beban_komisi_tp_curr = extract_two_numbers(text, "Beban Komisi - Tahun Pertama")
    beban_komisi_tl_prev, beban_komisi_tl_curr = extract_two_numbers(text, "Beban Komisi - Tahun Lanjutan")
    beban_komisi_ov_prev, beban_komisi_ov_curr = extract_two_numbers(text, "Beban Komisi - Overiding")
    jml_beban_asuransi_prev, jml_beban_asuransi_curr = extract_two_numbers(text, "Jumlah Beban Asuransi")
    laba_komp_prev, laba_komp_curr = extract_two_numbers(text, "Total Laba (Rugi) Komprehensif")
    solv_prev, solv_curr = extract_two_numbers(text, "Rasio Pencapaian Solvabilitas (%)")
    lik_prev, lik_curr = extract_two_numbers(text, "Rasio Likuiditas (%)")

    current_period = f"{args.yyyy}-{args.mm:02d}"
    prev_year = args.yyyy - 1
    prev_period = f"{prev_year}-{args.mm:02d}"
    rows = [
        {
            "periode": current_period,
            "jenis_asuransi": jenis,
            "nama_perusahaan": company,
            "aset": aset_curr,
            "ekuitas": ekuitas_curr,
            "pendapatan_premi": pend_premi_curr,
            "premi_reasuransi": premi_reasu_curr,
            "premi_neto": premi_neto_curr,
            "jumlah_pendapatan": jml_pend_curr,
            "beban_komisi_tahun_pertama": beban_komisi_tp_curr,
            "beban_komisi_tahun_lanjutan": beban_komisi_tl_curr,
            "beban_komisi_overiding": beban_komisi_ov_curr,
            "jumlah_beban_asuransi": jml_beban_asuransi_curr,
            "laba_rugi_komprehensif": laba_komp_curr,
            "rasio_solvabilitas": solv_curr,
            "rasio_likuiditas": lik_curr,
        },
        {
            "periode": prev_period,
            "jenis_asuransi": jenis,
            "nama_perusahaan": company,
            "aset": aset_prev,
            "ekuitas": ekuitas_prev,
            "pendapatan_premi": pend_premi_prev,
            "premi_reasuransi": premi_reasu_prev,
            "premi_neto": premi_neto_prev,
            "jumlah_pendapatan": jml_pend_prev,
            "beban_komisi_tahun_pertama": beban_komisi_tp_prev,
            "beban_komisi_tahun_lanjutan": beban_komisi_tl_prev,
            "beban_komisi_overiding": beban_komisi_ov_prev,
            "jumlah_beban_asuransi": jml_beban_asuransi_prev,
            "laba_rugi_komprehensif": laba_komp_prev,
            "rasio_solvabilitas": solv_prev,
            "rasio_likuiditas": lik_prev,
        },
    ]

    COMPANY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with COMPANY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="|")
        writer.writeheader()
        writer.writerows(rows)

    DATABASE_CSV.parent.mkdir(parents=True, exist_ok=True)
    upsert_database_csv(DATABASE_CSV, rows, COLUMNS)

    print(f"✓ Extracted metrics for {company}")
    print(f"  Company CSV: {COMPANY_CSV}")
    print(f"  Database CSV: {DATABASE_CSV}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
