"""Download financial reports for PT Kookmin Best Insurance Indonesia.

Note: this company publishes quarterly (not monthly) reports.
The script maps the target month to the appropriate quarter.
"""
import argparse
import logging
import sys
import tempfile
from pathlib import Path

from _downloader_base import (
    build_session, write_manifest, validate_pdf, current_timestamp
)

LOGGER = logging.getLogger("download_pt_kookmin_best_insurance_indonesia")
SOURCE_BASE = "https://www.kbfg.com"
SOURCE_URL = "https://www.kbfg.com/idn/ir/report/financial/list.jsp"
COMPANY_ID = "pt_kookmin_best_insurance_indonesia"
COMPANY_NAME = "PT Kookmin Best Insurance Indonesia"
CATEGORY = "asuransi_umum"


def month_to_quarter(month):
    return (month - 1) // 3 + 1


def build_pdf_url(year, month):
    q = month_to_quarter(month)
    return f"{SOURCE_BASE}/common/jsp/fileDownUtil.jsp?filepath=/data/bspl/{year}_{q}Q_BSPL.pdf"


def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--debug-html", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / "raw_pdf" / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{period}.pdf"

    q = month_to_quarter(args.month)
    pdf_url = build_pdf_url(args.year, args.month)
    LOGGER.info(f"Quarterly report Q{q} {args.year}: {pdf_url}")

    try:
        r = session.head(pdf_url, timeout=args.timeout, allow_redirects=True,
                         headers={"Referer": SOURCE_URL})
        if r.status_code != 200:
            reason = f"PDF URL returned HTTP {r.status_code} (quarterly report Q{q} may not be published yet)"
            LOGGER.warning(reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
                "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "no_pdf_found", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 0
    except Exception as e:
        reason = f"failed to reach PDF URL: {e}"
        LOGGER.error(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "failed", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download Q{q} {args.year} from {pdf_url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "already_exists", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with session.get(pdf_url, timeout=args.timeout, stream=True,
                         headers={"Referer": SOURCE_URL}) as response:
            status = response.status_code
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(output_dir), suffix=".part") as tmp:
                temp_path = Path(tmp.name)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
        data = temp_path.read_bytes()
        if not validate_pdf(data):
            temp_path.unlink()
            raise RuntimeError("Downloaded file is not a valid PDF")
        temp_path.replace(output_pdf)
        reason = f"HTTP {status} (Q{q} {args.year})"
        success = True
        LOGGER.info(f"Successfully downloaded to {output_pdf} ({len(data)} bytes)")
    except Exception as e:
        reason = str(e)
        success = False
        LOGGER.error(f"Download failed: {reason}")

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": "success" if success else "failed",
        "reason": reason, "timestamp": current_timestamp()
    }])
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
