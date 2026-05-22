"""Download financial reports for PT Perta Life Insurance."""
import argparse
import logging
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp
)

LOGGER = logging.getLogger("download_pt_perta_life_insurance")
SOURCE_URL = "https://pertalife.com/laporan-keuangan/#1778465946291-c76f0389-7845"
COMPANY_ID = "pt_perta_life_insurance"
COMPANY_NAME = "PT Perta Life Insurance"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def discover_perta_life_pdf(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL by selecting year dropdown + month list + document link."""
    month_name = MONTH_NAMES[month]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            time.sleep(2)

            # Scroll to reveal dropdown
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 400)")
                page.wait_for_timeout(300)

            # Find and click year dropdown
            # Look for select/dropdown element with year options
            selects = page.query_selector_all("select")
            year_select = None
            for sel in selects:
                options = sel.query_selector_all("option")
                for opt in options:
                    if str(year) in opt.inner_text():
                        year_select = sel
                        break
                if year_select:
                    break

            if year_select:
                year_select.select_option(str(year))
                page.wait_for_timeout(1000)

            # Find month link/button containing month name
            month_text = f"Laporan Keuangan – {month_name}"
            elements = page.query_selector_all("a, button")
            for elem in elements:
                if month_text in elem.inner_text():
                    # Click to open/download
                    with page.expect_download(timeout=timeout * 1000) as download_info:
                        elem.click()
                        page.wait_for_timeout(2000)

                    download = download_info.value
                    pdf_url = download.url
                    browser.close()
                    return pdf_url

            # If no direct link found, try generic extraction after dropdown selection
            html = page.content()
            browser.close()

            candidates = extract_pdf_links(html, SOURCE_URL, year, month)
            if candidates:
                return candidates[0].url

            return None

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
        LOGGER.error("Year and month (1-12) required")
        return 1
    
    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF from {SOURCE_URL}")

    # Try site-specific discovery first (dropdown + month selection)
    pdf_url = discover_perta_life_pdf(args.year, args.month, args.timeout)

    if not pdf_url:
        # Fallback to generic extraction via browser
        try:
            LOGGER.info("Fallback: trying generic extraction via browser")
            html, discovered_url = fetch_html_browser(SOURCE_URL, args.timeout)
            candidates = extract_pdf_links(html, discovered_url, args.year, args.month)
            if candidates:
                pdf_url = candidates[0].url
        except Exception as e:
            LOGGER.warning(f"Fallback also failed: {e}")

    if not pdf_url:
        reason = "no PDF discovered (dropdown selection or generic extraction)"
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
        return 0
    else:
        LOGGER.info(f"PDF already exists: {output_pdf}")
        return 0

if __name__ == "__main__":
    sys.exit(main())
