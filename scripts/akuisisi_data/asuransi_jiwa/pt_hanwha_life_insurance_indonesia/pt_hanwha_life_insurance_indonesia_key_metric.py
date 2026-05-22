#!/usr/bin/env python3
import argparse, csv, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _key_metric_helpers import upsert_database_csv
COLUMNS = ["periode","jenis_asuransi","nama_perusahaan","aset","ekuitas","pendapatan_premi","premi_reasuransi","premi_neto","jumlah_pendapatan","beban_komisi_tahun_pertama","beban_komisi_tahun_lanjutan","beban_komisi_overiding","jumlah_beban_asuransi","laba_rugi_komprehensif","rasio_solvabilitas","rasio_likuiditas"]
def extract_two_numbers(text: str, keyword: str):
    pattern = re.compile(rf"{re.escape(keyword)}\s+(\(?[0-9\.,%\-]+\)?)\s+(\(?[0-9\.,%\-]+\)?)", re.IGNORECASE)
    m = pattern.search(text)
    if not m: return None, None
    def norm(s: str) -> str:
        s = s.strip()
        return "-" + s[1:-1] if s.startswith("(") and s.endswith(")") else s
    return norm(m.group(1)), norm(m.group(2))
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yyyy", type=int, default=2026)
    parser.add_argument("--mm", type=int, default=4)
    args = parser.parse_args()
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    period_dir = PROJECT_ROOT / "data" / f"{args.yyyy}-{args.mm:02d}"
    company_dir = period_dir / "asuransi_jiwa" / "pt_hanwha_life_insurance_indonesia"
    INPUT_TXT = company_dir / f"pt_hanwha_life_insurance_indonesia_{args.yyyy}_{args.mm:02d}.txt"
    COMPANY_CSV = company_dir / f"pt_hanwha_life_insurance_indonesia_key_metric_{args.yyyy}_{args.mm:02d}.csv"
    DATABASE_CSV = period_dir / f"database_asuransi_jiwa_{args.yyyy}_{args.mm:02d}.csv"
    if not INPUT_TXT.exists(): return 1
    text = INPUT_TXT.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)
    company, jenis = "PT Hanwha Life Insurance Indonesia", "Asuransi Jiwa"
    aset_curr, aset_prev = extract_two_numbers(text, "Jumlah Aset")
    ekuitas_curr, ekuitas_prev = extract_two_numbers(text, "Jumlah Ekuitas")
    pend_premi_curr, pend_premi_prev = extract_two_numbers(text, "Pendapatan Premi")
    premi_reasu_curr, premi_reasu_prev = extract_two_numbers(text, "Premi Reasuransi")
    premi_neto_curr, premi_neto_prev = extract_two_numbers(text, "Jumlah Pendapatan Premi Neto")
    jml_pend_curr, jml_pend_prev = extract_two_numbers(text, "Jumlah Pendapatan")
    beban_komisi_tp_curr, beban_komisi_tp_prev = extract_two_numbers(text, "Beban Komisi - Tahun Pertama")
    beban_komisi_tl_curr, beban_komisi_tl_prev = extract_two_numbers(text, "Beban Komisi - Tahun Lanjutan")
    beban_komisi_ov_curr, beban_komisi_ov_prev = extract_two_numbers(text, "Beban Komisi")
    jml_beban_asuransi_curr, jml_beban_asuransi_prev = extract_two_numbers(text, "Jumlah Beban Asuransi")
    laba_komp_curr, laba_komp_prev = extract_two_numbers(text, "Total Laba.*Komprehensif|Laba.*Setelah Pajak")
    solv_curr, solv_prev = extract_two_numbers(text, "Rasio Pencapaian")
    lik_curr, lik_prev = extract_two_numbers(text, "Rasio Likuiditas")
    current_period = f"{args.yyyy}-{args.mm:02d}"
    prev_period = f"{args.yyyy-1}-{args.mm:02d}"
    rows = [{
        "periode": current_period, "jenis_asuransi": jenis, "nama_perusahaan": company,
        "aset": aset_curr, "ekuitas": ekuitas_curr, "pendapatan_premi": pend_premi_curr,
        "premi_reasuransi": premi_reasu_curr, "premi_neto": premi_neto_curr,
        "jumlah_pendapatan": jml_pend_curr, "beban_komisi_tahun_pertama": beban_komisi_tp_curr,
        "beban_komisi_tahun_lanjutan": beban_komisi_tl_curr, "beban_komisi_overiding": beban_komisi_ov_curr,
        "jumlah_beban_asuransi": jml_beban_asuransi_curr, "laba_rugi_komprehensif": laba_komp_curr,
        "rasio_solvabilitas": solv_curr, "rasio_likuiditas": lik_curr,
    }, {
        "periode": prev_period, "jenis_asuransi": jenis, "nama_perusahaan": company,
        "aset": aset_prev, "ekuitas": ekuitas_prev, "pendapatan_premi": pend_premi_prev,
        "premi_reasuransi": premi_reasu_prev, "premi_neto": premi_neto_prev,
        "jumlah_pendapatan": jml_pend_prev, "beban_komisi_tahun_pertama": beban_komisi_tp_prev,
        "beban_komisi_tahun_lanjutan": beban_komisi_tl_prev, "beban_komisi_overiding": beban_komisi_ov_prev,
        "jumlah_beban_asuransi": jml_beban_asuransi_prev, "laba_rugi_komprehensif": laba_komp_prev,
        "rasio_solvabilitas": solv_prev, "rasio_likuiditas": lik_prev,
    }]
    COMPANY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with COMPANY_CSV.open("w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=COLUMNS, delimiter="|").writeheader()
        csv.DictWriter(f, fieldnames=COLUMNS, delimiter="|").writerows(rows)
    DATABASE_CSV.parent.mkdir(parents=True, exist_ok=True)
    upsert_database_csv(DATABASE_CSV, rows, COLUMNS)
    return 0
if __name__ == "__main__": sys.exit(main())
