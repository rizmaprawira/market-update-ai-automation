"""Download financial reports for PT Equity Life Indonesia."""
import argparse
import logging
import sys
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp,
    MONTH_NAMES
)

LOGGER = logging.getLogger("download_pt_equity_life_indonesia")
SOURCE_URL = "https://www.equity.co.id/about/report"
COMPANY_ID = "pt_equity_life_indonesia"
COMPANY_NAME = "PT Equity Life Indonesia"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES_ENGLISH = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

def discover_equity_life_pdf(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL by interacting with custom combobox dropdowns."""
    month_name = MONTH_NAMES_ENGLISH[month]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Get the first download button section (Laporan Keuangan / Financial Report)
            report_section = page.locator("text=Laporan Keuangan").first.locator("..")

            # Find all combobox buttons in the report section
            comboboxes = report_section.locator("button[role='combobox']")
            count = comboboxes.count()

            LOGGER.info(f"Found {count} combobox dropdowns in report section")

            if count < 3:
                raise RuntimeError(f"Expected at least 3 combobox dropdowns, found {count}")

            # Click and select year (usually second combobox)
            year_combobox = comboboxes.nth(1)
            year_combobox.click(timeout=2000)
            page.wait_for_timeout(500)

            # Select year from dropdown
            year_option = page.locator(f"[role='option']:has-text('{year}')").first
            year_option.click(timeout=2000)
            page.wait_for_timeout(1000)

            # Click and select month (usually third combobox)
            month_combobox = comboboxes.nth(2)
            month_combobox.click(timeout=2000)
            page.wait_for_timeout(500)

            # Select month from dropdown (use English month name)
            month_option = page.locator(f"[role='option']:has-text('{month_name}')").first
            month_option.click(timeout=2000)
            page.wait_for_timeout(1500)

            # Find the download button in the report section
            download_button = report_section.locator("button:has-text('Unduh')").first

            # Check if download button is now enabled
            is_enabled = not download_button.is_disabled()

            if not is_enabled:
                LOGGER.warning("Download button is still disabled after dropdown selection")
            else:
                LOGGER.info("Download button is enabled, proceeding with download")

            # Try to intercept the download or find the PDF URL
            pdf_url = None

            # Listen for PDF responses
            pdf_responses = []
            def handle_response(response):
                try:
                    if 'application/pdf' in response.headers.get('content-type', '').lower():
                        pdf_responses.append(response.url)
                except:
                    pass

            page.on('response', handle_response)

            # Click the download button
            try:
                download_button.click(timeout=2000)
                page.wait_for_timeout(3000)
            except Exception as e:
                LOGGER.warning(f"Failed to click download button: {e}")

            # Check if we captured a PDF response
            if pdf_responses:
                pdf_url = pdf_responses[0]
                LOGGER.info(f"Captured PDF response: {pdf_url}")
                browser.close()
                return pdf_url

            # Fallback: extract from HTML after dropdown interaction
            html = page.content()
            browser.close()

            candidates = extract_pdf_links(html, SOURCE_URL, year, month)
            if candidates:
                return candidates[0].url

            raise RuntimeError("No PDF URL discovered after dropdown interaction")

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

    if not args.year or not args.month or not 1 <= args.month <= 12:
        LOGGER.error("Year and month are required; month must be 1-12")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF from {SOURCE_URL}")

    # Try site-specific discovery with dropdown interaction
    pdf_url = discover_equity_life_pdf(args.year, args.month, args.timeout)

    if not pdf_url:
        reason = "no PDF discovered (dropdown interaction failed)"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Discovered: {pdf_url[:80]}")

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

    try:
        http_status, file_size = download_pdf(
            session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
        reason = (
            f"HTTP {http_status} ({file_size} bytes)"
            if http_status is not None
            else f"existing valid PDF kept ({file_size} bytes)"
        )
    except Exception as e:
        LOGGER.warning(f"Direct download failed ({e}), trying Playwright fetch")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                response = page.goto(pdf_url, timeout=args.timeout * 1000, wait_until="commit")
                page.wait_for_timeout(2000)
                pdf_bytes = page.pdf()
                output_pdf.parent.mkdir(parents=True, exist_ok=True)
                output_pdf.write_bytes(pdf_bytes)
                file_size = len(pdf_bytes)
                browser.close()
                status = "downloaded"
                reason = f"Playwright PDF export ({file_size} bytes)"
                http_status = 200
        except Exception as e2:
            LOGGER.error(f"Playwright fetch failed: {e2}")
            status = "error"
            reason = f"Failed to download via HTTP and Playwright: {e2}"
            http_status = None
            file_size = 0

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if http_status is not None and status == "downloaded":
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
        return 0
    elif status == "skipped_existing":
        LOGGER.info(f"PDF already exists, keeping cached version")
        return 0
    else:
        LOGGER.error(f"Failed to download: {reason}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
