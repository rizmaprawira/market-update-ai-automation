"""Download financial reports for PT Kookmin Best Insurance Indonesia.

Note: Indonesian branch publishes monthly reports via direct URLs.
Uses Indonesian month names in the URL path.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, write_manifest, current_timestamp,
    MONTH_LABELS, PDFCandidate
)

LOGGER = logging.getLogger("download_pt_kookmin_best_insurance_indonesia")
SOURCE_URL = "https://ebusiness.kbinsure.co.id:9191/assets/img/web_official/content/about_us/financial_statement/en/"
COMPANY_ID = "pt_kookmin_best_insurance_indonesia"
COMPANY_NAME = "PT Kookmin Best Insurance Indonesia"
CATEGORY = "asuransi_umum"


def construct_kookmin_url(year, month):
    """Construct direct URL for Kookmin monthly report.

    Uses Indonesian month names: Januari, Februari, Maret, April, etc.
    Format: Laporan_Bulanan_[MONTH]_[YEAR].pdf
    """
    month_label = MONTH_LABELS[month]
    filename = f"Laporan_Bulanan_{month_label}_{year}.pdf"
    return f"{SOURCE_URL}{filename}"


def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, no download")
    parser.add_argument("--dry-run", action="store_true", help="Validate download without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failure")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    month_label = MONTH_LABELS[args.month]
    pdf_url = construct_kookmin_url(args.year, args.month)

    LOGGER.info(f"Constructing direct URL for {month_label} {args.year}")
    LOGGER.info(f"URL: {pdf_url}")

    if args.discover_only:
        LOGGER.info(f"Discovery complete: {month_label} {args.year}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discovery complete",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {pdf_url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    from _downloader_base import download_pdf

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        http_status, file_size = download_pdf(
            session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
        )
        success = True
        reason = (
            f"downloaded monthly report ({http_status}, bytes={file_size})"
            if http_status is not None
            else f"existing valid PDF kept (bytes={file_size})"
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
    except Exception as e:
        success = False
        reason = str(e)
        status = "error"
        http_status = None

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status,
        "reason": reason, "timestamp": current_timestamp()
    }])

    if success and http_status is not None:
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
        return 0
    elif success:
        LOGGER.info(f"Kept existing valid PDF at {output_pdf}")
        return 0
    else:
        LOGGER.error(f"Download failed: {reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
