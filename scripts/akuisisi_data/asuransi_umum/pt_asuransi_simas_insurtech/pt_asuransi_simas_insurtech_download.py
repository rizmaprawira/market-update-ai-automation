"""Download financial reports for PT Asuransi Simas Insurtech."""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp, MONTH_LABELS
)

LOGGER = logging.getLogger("download_pt_asuransi_simas_insurtech")
SOURCE_URL = "https://simasinsurtech.com/tentang-kami"
FALLBACK_URL = "https://simasinsurtech.com/tentang-kami/laporan-keuangan-simasinsurtech/"
COMPANY_ID = "pt_asuransi_simas_insurtech"
COMPANY_NAME = "PT Asuransi Simas Insurtech"
CATEGORY = "asuransi_umum"

MONTH_NAMES_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def fetch_simas_with_dropdown_selection(source_url, year, month, timeout):
    """Fetch Simas Insurtech PDF URL by selecting year and month dropdowns."""
    from playwright.sync_api import sync_playwright
    import tempfile
    import os

    month_name = MONTH_NAMES_ID[month]

    with tempfile.TemporaryDirectory() as temp_dir:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            try:
                page.goto(source_url, wait_until="networkidle", timeout=timeout * 1000)

                LOGGER.info("Scrolling down to find dropdown section")
                page.evaluate("window.scrollBy(0, 2000)")
                page.wait_for_timeout(1500)

                LOGGER.info(f"Selecting year: {year}")
                year_select = page.locator("select").first
                year_select.select_option(value=str(year))
                page.wait_for_timeout(1000)

                LOGGER.info(f"Selecting month: {month_name}")
                month_select = page.locator("select").nth(1)
                month_select.select_option(value=month_name)
                page.wait_for_timeout(1000)

                LOGGER.info("Clicking Download button")
                download_button = page.locator("button, a").filter(has_text="Download").first

                with page.expect_download() as download_info:
                    download_button.click()

                download = download_info.value
                download_path = download.path()
                pdf_url = download.url

                LOGGER.info(f"PDF downloaded to: {download_path}")
                LOGGER.info(f"PDF URL: {pdf_url}")

                browser.close()
                return pdf_url
            except Exception as e:
                LOGGER.error(f"Error fetching with dropdowns: {e}")
                browser.close()
                raise

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

    discovered_url = SOURCE_URL
    pdf_url = None
    fetch_error = None

    LOGGER.info(f"Fetching from {SOURCE_URL}")

    try:
        LOGGER.info("Using Playwright with dropdown selection")
        pdf_url = fetch_simas_with_dropdown_selection(SOURCE_URL, args.year, args.month, args.timeout)
    except Exception as e:
        fetch_error = str(e)
        LOGGER.warning(f"Primary URL failed: {fetch_error}")
        if SOURCE_URL != FALLBACK_URL:
            LOGGER.info(f"Trying fallback URL: {FALLBACK_URL}")
            try:
                pdf_url = fetch_simas_with_dropdown_selection(FALLBACK_URL, args.year, args.month, args.timeout)
                fetch_error = None
            except Exception as e2:
                fetch_error = str(e2)
                LOGGER.error(f"Fallback URL also failed: {fetch_error}")

        if fetch_error:
            reason = f"failed to fetch: {fetch_error}"
            if args.debug_html:
                write_debug_html(debug_dir, "", reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
                "pdf_url": "", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "error", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 1

    if not pdf_url:
        reason = "no PDF URL found"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Selected: {pdf_url}")

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
