"""Download financial reports for PT Bhinneka Life Indonesia."""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, download_pdf, write_manifest, current_timestamp
)

LOGGER = logging.getLogger("download_pt_bhinneka_life_indonesia")
SOURCE_URL = "https://www.bhinnekalife.com/id/laporan-keuangan"
COMPANY_ID = "pt_bhinneka_life_indonesia"
COMPANY_NAME = "PT Bhinneka Life Indonesia"
CATEGORY = "asuransi_jiwa"

def get_bhinneka_report_url(year: int, month: int) -> str:
    """Use Playwright to find and construct download URL for Bhinneka monthly report."""
    try:
        from playwright.sync_api import sync_playwright
        from urllib.parse import quote

        LOGGER.info(f"Using Playwright to discover {year}-{month:02d} report...")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            try:
                # Load main page
                page.goto(SOURCE_URL, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                # Click Bulanan tab
                page.click("button:has-text('Bulanan')")
                page.wait_for_timeout(2000)

                # Find and click year accordion (e.g., "Laporan Keuangan Bulanan Tahun 2026")
                year_button_text = f"Laporan Keuangan Bulanan Tahun {year}"
                try:
                    page.click(f"button:has-text('{year_button_text}')")
                    page.wait_for_timeout(2000)
                except:
                    LOGGER.warning(f"Could not find accordion for year {year}")
                    browser.close()
                    return None

                # Get all download links for this month
                month_names = ["januari", "februari", "maret", "april", "mei", "juni",
                              "juli", "agustus", "september", "oktober", "november", "desember"]
                month_name_id = month_names[month - 1]

                # Get all data-folder attributes
                links = page.query_selector_all("a.btn-download[data-folder*='bulanan']")
                for link in links:
                    folder = link.get_attribute("data-folder")
                    if folder and month_name_id in folder.lower() and str(year) in folder:
                        # Construct download URL
                        base_url = "https://www.bhinnekalife.com/admin/bli/apt/myfile/download_file_s3/"
                        download_url = base_url + quote(folder, safe='/')
                        browser.close()
                        return download_url

                browser.close()
                return None
            except Exception as e:
                browser.close()
                LOGGER.error(f"Playwright error: {e}")
                return None
    except ImportError:
        LOGGER.error("Playwright not available")
        return None

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", type=int, help="Target year")
    parser.add_argument("--yyyy", dest="year", type=int, help="Target year (alias for --year)")
    parser.add_argument("--month", type=int, help="Target month (1-12)")
    parser.add_argument("--mm", dest="month", type=int, help="Target month 1-12 (alias for --month)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no download")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, return 0")
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

    LOGGER.info(f"Fetching from {SOURCE_URL}")

    # Get download URL using Playwright interaction
    pdf_url = get_bhinneka_report_url(args.year, args.month)

    if not pdf_url:
        reason = "no PDF found for this month"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Found report: {pdf_url[:80]}...")
    
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

    if http_status is not None:
        status = "downloaded"
        reason = f"HTTP {http_status} ({file_size} bytes)"
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
        success = True
    else:
        status = "skipped_existing"
        reason = f"existing valid PDF kept ({file_size} bytes)"
        LOGGER.info(f"PDF already exists and is valid: {output_pdf}")
        success = True

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
