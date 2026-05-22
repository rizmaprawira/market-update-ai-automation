"""Download financial reports for PT Pacific Life Insurance."""
import argparse
import logging
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, download_pdf, write_manifest, current_timestamp
)

LOGGER = logging.getLogger("download_pt_pacific_life_insurance")
SOURCE_URL = "https://www.pacificlife.co.id/laporan-keuangan"
COMPANY_ID = "pt_pacific_life_insurance"
COMPANY_NAME = "PT Pacific Life Insurance"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def discover_pacific_life_pdf(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL by selecting dropdowns and extracting file path."""
    month_name = MONTH_NAMES[month]
    target_month_text = month_name  # e.g., "Maret" for March

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            time.sleep(1)

            # Select "Laporan Keuangan" from report type dropdown
            page.select_option("#financial_reports_type_selector", "Laporan Keuangan")
            time.sleep(0.5)

            # Select year from year dropdown
            page.select_option("#financial_reports_year_selector", str(year))
            time.sleep(1)

            # Get the rendered HTML to find the matching month option
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Find the file dropdown and look for the month that matches
            file_select = soup.find('select', id='financial_report_detail_types')
            if not file_select:
                browser.close()
                return None

            options = file_select.find_all('option')
            target_file_path = None

            for opt in options:
                text = opt.get_text(strip=True)
                value = opt.get('value', '')

                # Match the month name in the option text
                if target_month_text in text and str(year) in value:
                    target_file_path = value
                    LOGGER.info(f"Found file option: {text} → {value}")
                    break

            browser.close()

            if not target_file_path or target_file_path == "None":
                return None

            # Construct the full URL
            pdf_url = f"https://www.pacificlife.co.id/{target_file_path}"
            LOGGER.info(f"Discovered PDF: {pdf_url}")
            return pdf_url

    except Exception as e:
        LOGGER.warning(f"Failed to discover via Playwright: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no download")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, return 0")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
    parser.add_argument("--use-browser", action="store_true", help="Use Playwright browser rendering")
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failure")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not args.year or not args.month or not (1 <= args.month <= 12):
        LOGGER.error("Year and month (1-12) are required")
        return 1
    
    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    LOGGER.info(f"Discovering PDF for {MONTH_NAMES[args.month]} {args.year}")

    pdf_url = discover_pacific_life_pdf(args.year, args.month, args.timeout)

    if not pdf_url:
        reason = "no PDF found for target period"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Discovered: {pdf_url}")

    if args.discover_only:
        LOGGER.info("Discover-only mode: stopping after discovery")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discover-only mode",
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

    http_status, file_size = download_pdf(
        session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
    )

    status = "downloaded" if http_status is not None else "skipped_existing"
    reason = (
        f"HTTP {http_status} ({file_size} bytes)"
        if http_status is not None
        else f"existing valid PDF kept ({file_size} bytes)"
    )

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if http_status is not None:
        LOGGER.info(f"Successfully downloaded to {output_pdf} ({file_size} bytes)")
        return 0
    else:
        LOGGER.info(f"Skipped existing PDF at {output_pdf}")
        return 0

if __name__ == "__main__":
    sys.exit(main())
