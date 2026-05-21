"""Download financial reports for PT Avrist General Insurance."""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp,
    MONTH_LABELS
)

LOGGER = logging.getLogger("download_pt_avrist_general_insurance")
SOURCE_URL = "https://www.avrist.com/tentang-avrist-life/tentang-avrist-life?tab=Laporan+Perusahaan"
API_URL = "https://avrist.com/api-front/api/content/filter/lap-perusahaan"
COMPANY_ID = "pt_avrist_general_insurance"
COMPANY_NAME = "PT Avrist General Insurance"
CATEGORY = "asuransi_umum"


def find_avrist_pdf_url(year, month, session, timeout):
    """Query Avrist API to find the PDF URL for a given month/year."""
    import json

    month_label = MONTH_LABELS[month]

    payload = {
        "includeAttributes": True,
        "searchRequest": {
            "keyword": "",
            "fieldIds": ["nama-file-laporan"],
            "postData": True
        },
        "filters": [],
        "category": ""
    }

    try:
        response = session.post(API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        categories = data.get('data', {}).get('categoryList', {})

        # Look in Laporan Keuangan for the month/year
        for item in categories.get('Laporan Keuangan', []):
            content = item.get('contentData', [])
            title = item.get('title', '')

            year_val = None
            month_val = None
            file_ref = None

            for field in content:
                field_id = field.get('fieldId', '')
                value = field.get('value', '')

                if field_id == 'tahun':
                    year_val = value
                elif field_id == 'bulan':
                    month_val = value
                elif field_id == 'file-laporan':
                    file_ref = value

            # Match year and month
            if str(year_val) == str(year):
                # Check if month matches (either full name or abbreviated)
                if month_val and (month_val.lower() == month_label.lower() or month_val.lower() == month_label[:3].lower()):
                    # Extract file URL from file_ref
                    try:
                        file_data = json.loads(file_ref)
                        if isinstance(file_data, list) and len(file_data) > 0:
                            img_url = file_data[0].get('imageUrl', '')
                            if img_url:
                                pdf_url = f"https://avrist.com/api-cms/files/get/{img_url}"
                                LOGGER.info(f"Found API URL: {title}")
                                return pdf_url
                    except Exception as e:
                        LOGGER.debug(f"Could not parse file reference: {e}")

        return None
    except Exception as e:
        LOGGER.debug(f"API query failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, no download")
    parser.add_argument("--dry-run", action="store_true", help="Validate download without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
    parser.add_argument("--use-browser", action="store_true", help="Use Playwright browser rendering")
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
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Attempting API-based discovery for {period}")
    pdf_url = find_avrist_pdf_url(args.year, args.month, session, args.timeout)
    discovered_url = pdf_url or SOURCE_URL

    if not pdf_url:
        reason = "no PDF found via API"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Found PDF URL via API")

    if args.discover_only:
        LOGGER.info("Discovery complete (--discover-only mode)")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discovery complete",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {pdf_url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    http_status, file_size = download_pdf(
        session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
    )

    status = "downloaded" if http_status is not None else "skipped_existing"
    reason = (
        f"HTTP {http_status} ({file_size} bytes)"
        if http_status is not None
        else f"existing valid ({file_size} bytes)"
    )

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if http_status is not None:
        LOGGER.info(f"Successfully downloaded to {output_pdf} ({file_size} bytes)")
    else:
        LOGGER.info(f"Using existing valid PDF at {output_pdf}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
