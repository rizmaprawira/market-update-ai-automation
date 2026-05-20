#!/usr/bin/env python3
"""Plot per-metric grouped bar charts for reinsurance companies (2026-04 vs 2025-04)."""

from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

METRICS = [
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
RATIO_METRICS = {"rasio_solvabilitas", "rasio_likuiditas"}
NA_MARKERS = {"", "N/A", "NA", "-", "NONE", "NULL"}
COLUMN_NAMES = [
    "tahun-bulan",
    "jenis_asuransi",
    "perusahaan",
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


def normalize_company_name(name: str) -> str:
    text = (name or "").upper()
    text = text.replace("PT.", "PT ")
    text = text.replace("TBK", "")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_numeric(raw: str, is_ratio: bool) -> float:
    if raw is None:
        return np.nan
    s = str(raw).strip()
    if s.upper() in NA_MARKERS:
        return np.nan

    s = s.replace("−", "-")

    if is_ratio:
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        elif "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
        if "," in s and "." not in s:
            s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return np.nan


def load_pipe_csv(path: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="|")
        header = next(reader, None)
        if not header:
            raise ValueError(f"File kosong: {path}")
        if len(header) != len(COLUMN_NAMES):
            raise ValueError(f"Header tidak sesuai ekspektasi ({len(header)} kolom): {header}")

        for idx, parts in enumerate(reader, start=2):
            if not parts:
                continue
            if len(parts) != len(header):
                print(f"[WARN] Skip baris {idx} (kolom {len(parts)} != {len(header)})")
                continue
            rows.append(dict(zip(header, parts)))

    return pd.DataFrame(rows)


def load_source_company_order(output_dir: Path) -> list[str]:
    source_paths = sorted(output_dir.glob("*_https_/data_output.csv"))
    names: list[str] = []
    for p in source_paths:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter="|")
            for parts in reader:
                if len(parts) >= 3 and parts[2].strip():
                    names.append(parts[2].strip())
                    break

    if not names:
        raise ValueError("Tidak menemukan company dari source 001..008")

    # Preserve order, unique by normalized name.
    ordered_unique: list[str] = []
    seen: set[str] = set()
    for n in names:
        key = normalize_company_name(n)
        if key not in seen:
            seen.add(key)
            ordered_unique.append(key)
    return ordered_unique


def pick_best_duplicate(group: pd.DataFrame) -> pd.Series:
    tmp = group.copy()
    tmp["_na_count"] = tmp[METRICS].isna().sum(axis=1)
    tmp["_row_order"] = np.arange(len(tmp))
    best = tmp.sort_values(["_na_count", "_row_order"], ascending=[True, False]).iloc[0]
    return best.drop(labels=["_na_count", "_row_order"])


def format_value(v: float, is_ratio: bool) -> str:
    if pd.isna(v):
        return "N/A"
    if is_ratio:
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(round(v)):,}".replace(",", ".")


def plot_metric(df: pd.DataFrame, metric: str, companies_order: list[str], output_path: Path, period_prev: str, period_curr: str) -> None:
    metric_df = df[df["perusahaan_norm"].isin(companies_order)].copy()

    pivot = metric_df.pivot(index="perusahaan_norm", columns="tahun-bulan", values=metric)
    pivot = pivot.reindex(companies_order)

    display_names = (
        metric_df.groupby("perusahaan_norm", as_index=False)["perusahaan"]
        .first()
        .set_index("perusahaan_norm")["perusahaan"]
        .reindex(companies_order)
        .fillna("-")
    )

    x = np.arange(len(companies_order), dtype=float)
    bar_width = 0.36
    y_prev = pivot.get(period_prev, pd.Series(np.nan, index=companies_order)).astype(float).values
    y_curr = pivot.get(period_curr, pd.Series(np.nan, index=companies_order)).astype(float).values

    y_all = np.array([v for v in np.concatenate([y_prev, y_curr]) if not math.isnan(v)])
    if y_all.size == 0:
        y_min, y_max = -1.0, 1.0
    else:
        ymin_raw = float(np.min(y_all))
        ymax_raw = float(np.max(y_all))
        if ymin_raw == ymax_raw:
            pad = max(1.0, abs(ymax_raw) * 0.2)
            y_min, y_max = ymin_raw - pad, ymax_raw + pad
        else:
            pad = (ymax_raw - ymin_raw) * 0.15
            y_min, y_max = ymin_raw - pad, ymax_raw + pad

    plt.figure(figsize=(16, 8))
    bars_prev = plt.bar(x - bar_width / 2, y_prev, width=bar_width, color="#4C78A8", label=period_prev)
    bars_curr = plt.bar(x + bar_width / 2, y_curr, width=bar_width, color="#F58518", label=period_curr)

    plt.title(f"{metric} - {period_prev} vs {period_curr}")
    plt.xticks(x, display_names.values, rotation=25, ha="right")
    plt.ylabel(metric)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.35)
    plt.ylim(y_min, y_max)

    label_offset = (y_max - y_min) * 0.02 if y_max != y_min else 0.1

    for bars, values in ((bars_prev, y_prev), (bars_curr, y_curr)):
        for bar, val in zip(bars, values):
            x_center = bar.get_x() + bar.get_width() / 2
            if math.isnan(val):
                plt.text(x_center, 0 + label_offset, "N/A", ha="center", va="bottom", fontsize=8, rotation=90)
                continue

            va = "bottom" if val >= 0 else "top"
            y_pos = val + label_offset if val >= 0 else val - label_offset
            plt.text(
                x_center,
                y_pos,
                format_value(val, metric in RATIO_METRICS),
                ha="center",
                va=va,
                fontsize=8,
                rotation=90,
            )

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def build_company_order(df: pd.DataFrame, preferred_norm_names: list[str]) -> list[str]:
    company_summary = (
        df.groupby("perusahaan_norm", as_index=False)
        .agg(
            completeness=("aset", lambda s: int(s.notna().sum())),
            periods=("tahun-bulan", lambda s: sorted(set(s))),
        )
    )

    available = set(df["perusahaan_norm"].unique())
    order = [n for n in preferred_norm_names if n in available]

    if len(order) < 8:
        candidates = company_summary.copy()
        candidates["has_both_periods"] = candidates["periods"].apply(lambda p: len(p) >= 2)
        candidates = candidates.sort_values(["has_both_periods", "completeness", "perusahaan_norm"], ascending=[False, False, True])
        for name in candidates["perusahaan_norm"]:
            if name not in order:
                order.append(name)
            if len(order) == 8:
                break

    return order[:8]


def prepare_data(input_csv: Path, period_prev: str, period_curr: str) -> tuple[pd.DataFrame, int, int]:
    raw_df = load_pipe_csv(input_csv)
    n_raw = len(raw_df)

    raw_df = raw_df[raw_df["tahun-bulan"].isin([period_prev, period_curr])].copy()
    raw_df["perusahaan_norm"] = raw_df["perusahaan"].apply(normalize_company_name)

    for metric in METRICS:
        raw_df[metric] = raw_df[metric].apply(lambda v: parse_numeric(v, metric in RATIO_METRICS))

    dedup_df = (
        raw_df.groupby(["perusahaan_norm", "tahun-bulan"], as_index=False, group_keys=False)
        .apply(pick_best_duplicate)
        .reset_index(drop=True)
    )

    n_final = len(dedup_df)
    return dedup_df, n_raw, n_final


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot all reinsurance metrics per company with yearly comparison.")
    parser.add_argument(
        "--input",
        default="output_2026-04/data_konsolidasi_2026-04.csv",
        help="Input consolidated CSV (pipe-delimited)",
    )
    parser.add_argument(
        "--output-dir",
        default="output_2026-04/plots_2026-04",
        help="Directory to write PNG charts",
    )
    parser.add_argument("--period-current", default="2026-04", help="Current period")
    parser.add_argument("--period-previous", default="2025-04", help="Previous period")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_csv = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input file tidak ditemukan: {input_csv}")

    output_dir.mkdir(parents=True, exist_ok=True)

    df, n_raw, n_final = prepare_data(input_csv, args.period_previous, args.period_current)

    preferred_order = load_source_company_order(input_csv.parent)
    companies_order = build_company_order(df, preferred_order)

    if len(companies_order) < 8:
        raise ValueError(f"Perusahaan unik kurang dari 8 setelah cleansing ({len(companies_order)})")

    df = df[df["perusahaan_norm"].isin(companies_order)].copy()

    generated: list[str] = []
    for metric in METRICS:
        out_png = output_dir / f"{metric}.png"
        plot_metric(df, metric, companies_order, out_png, args.period_previous, args.period_current)
        generated.append(out_png.name)

    print("=== SUMMARY ===")
    print(f"Input CSV         : {input_csv}")
    print(f"Rows awal         : {n_raw}")
    print(f"Rows setelah dedup: {n_final}")
    print(f"Perusahaan plot   : {len(companies_order)}")
    print("Company order     :")
    for i, n in enumerate(companies_order, start=1):
        print(f"  {i}. {n}")
    print(f"Output dir        : {output_dir}")
    print(f"Total plot        : {len(generated)}")


if __name__ == "__main__":
    main()
