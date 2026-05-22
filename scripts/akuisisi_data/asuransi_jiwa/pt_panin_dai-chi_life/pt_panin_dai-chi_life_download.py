"""Download financial reports for PT Panin Dai-Chi Life Insurance."""
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

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_panin_dai-chi_life")
SOURCE_URL = "https://www.panindai-ichilife.co.id/id/laporan-keuangan"
COMPANY_ID = "pt_panin_dai-chi_life"
COMPANY_NAME = "PT Panin Dai-Chi Life"
CATEGORY = "asuransi_jiwa"

def discover_panin_daichi_pdf(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL by selecting year and month grids, then capturing download."""
    month_name = MONTH_LABELS[month]

    try:
        with sync_playwright() as p:
            # Launch browser with additional options to bypass anti-bot
            browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.set_extra_http_headers({
                "Referer": "https://www.panindai-ichilife.co.id/",
                "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            })

            LOGGER.info(f"Navigating to {SOURCE_URL}")
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="networkidle")
            time.sleep(2)

            # Step 1: Click year selection (grid-based year buttons)
            LOGGER.info(f"Looking for year {year} in page")
            year_str = str(year)

            # Try to find year by text in various element types
            year_selectors = [
                f"text={year_str}",
                f"button:has-text('{year_str}')",
                f"div:has-text('{year_str}')",
            ]

            year_clicked = False
            for selector in year_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible():
                        LOGGER.info(f"Clicking year element: {year_str}")
                        element.click(force=True)
                        year_clicked = True
                        time.sleep(1)
                        break
                except:
                    continue

            if not year_clicked:
                LOGGER.warning(f"Could not find year {year_str}")
                context.close()
                browser.close()
                return None

            # Step 2: Click month selection (grid-based month buttons)
            LOGGER.info(f"Looking for month {month_name} {year}")
            month_selectors = [
                f"text=LAPORAN KEUANGAN {month_name.upper()} {year}",
                f"button:has-text('{month_name.upper()}')",
                f"div:has-text('{month_name.upper()}')",
            ]

            month_clicked = False
            for selector in month_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible():
                        LOGGER.info(f"Clicking month element")
                        element.click(force=True)
                        month_clicked = True
                        time.sleep(1)
                        break
                except:
                    continue

            if not month_clicked:
                LOGGER.warning(f"Could not find month {month_name}")
                context.close()
                browser.close()
                return None

            # Step 3: Find and click "Download PDF" or "Download" button
            LOGGER.info("Looking for download button")
            download_selectors = [
                "text=Download PDF",
                "text=Download Pdf",
                "text=Download",
                "button:has-text('Download')",
                "button:has-text('Unduh')",
                "a:has-text('Download')",
            ]

            pdf_url = None
            for selector in download_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible():
                        LOGGER.info(f"Clicking download button with selector: {selector}")

                        with page.expect_download(timeout=timeout * 1000) as download_info:
                            element.click(force=True)
                            time.sleep(2)

                        download = download_info.value
                        pdf_url = download.url
                        LOGGER.info(f"Captured download URL: {pdf_url}")
                        break
                except Exception as e:
                    LOGGER.debug(f"Selector {selector} failed: {e}")
                    continue

            context.close()
            browser.close()
            return pdf_url

    except Exception as e:
        LOGGER.warning(f"Failed to discover via Playwright: {e}")
        import traceback
        LOGGER.debug(traceback.format_exc())
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

    if not args.year or not args.month:
        LOGGER.error("Year and month are required")
        return 1

    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1
    
    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF using Playwright year/month grid selection")

    # Use Playwright to discover PDF by selecting year/month grids
    pdf_url = discover_panin_daichi_pdf(args.year, args.month, args.timeout)

    if not pdf_url:
        reason = "no PDF found after year/month selection"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Discovered PDF URL: {pdf_url}")

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
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "existing valid PDF kept",
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

    if status == "downloaded":
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
    else:
        LOGGER.info(f"Using existing PDF: {output_pdf}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
