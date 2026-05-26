"""Download financial reports for PT Indolife Pensiontama."""
import argparse
import logging
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp
)

LOGGER = logging.getLogger("download_pt_indolife_pensiontama")
SOURCE_URL = "https://indolife.co.id/Read/Detail/laporan--perusahaan"
COMPANY_ID = "pt_indolife_pensiontama"
COMPANY_NAME = "PT Indolife Pensiontama"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES = {
    1: "JANUARI", 2: "FEBRUARI", 3: "MARET", 4: "APRIL",
    5: "MEI", 6: "JUNI", 7: "JULI", 8: "AGUSTUS",
    9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DESEMBER"
}

MONTH_DAYS = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
}

def discover_indolife_pdf(year: int, month: int, session, timeout: int = 30) -> str:
    """Discover PDF URL using browser rendering + strict period filtering."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Use longer timeout for page load - Indolife site is slow
        page_timeout = max(timeout * 1000, 60000)
        page.goto(SOURCE_URL, timeout=page_timeout, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        html = page.content()
        browser.close()

        soup = BeautifulSoup(html, "html.parser")
        target_month_name = MONTH_NAMES[month]

        # Find all PDF links
        candidates = []
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            href = link.get('href', '')

            # Must contain: "Laporan Keuangan", target month name, and target year
            if "laporan keuangan" in text.lower() and target_month_name in text.upper() and str(year) in text:
                # Ensure it's a PDF link
                if href.lower().endswith('.pdf') or '/Content/FileUploads/' in href:
                    full_url = href if href.startswith('http') else f"https://indolife.co.id{href}"
                    candidates.append(full_url)

        if candidates:
            return candidates[0]

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
        LOGGER.error("Year and month (1-12) are required")
        return 1

    logging.getLogger("playwright").setLevel(logging.WARNING)
    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF for {args.year}-{args.month:02d}")

    try:
        pdf_url = discover_indolife_pdf(args.year, args.month, session, timeout=args.timeout)
        discovered_url = SOURCE_URL

        if not pdf_url:
            reason = "no matching PDF found in dropdown"
            LOGGER.warning(reason)
            if args.debug_html:
                write_debug_html(debug_dir, "", reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
                "pdf_url": "", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "not_found", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 1

        LOGGER.info(f"Found PDF: {pdf_url}")

        if args.discover_only:
            LOGGER.info("Discover-only mode: stopping after discovery")
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
                "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "discover_only", "reason": "discover-only mode",
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
            else f"existing valid PDF kept ({file_size} bytes)"
        )

        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": status, "reason": reason,
            "timestamp": current_timestamp()
        }])

        if http_status is not None:
            LOGGER.info(f"Successfully downloaded to {output_pdf}")
        else:
            LOGGER.info(f"PDF already exists, skipped download")

        return 0

    except Exception as e:
        reason = f"error during discovery/download: {e}"
        LOGGER.error(reason)
        if args.debug_html:
            write_debug_html(debug_dir, "", reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "error", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

if __name__ == "__main__":
    sys.exit(main())
