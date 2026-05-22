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

def discover_indolife_pdf(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL using Playwright dropdown interaction."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        try:
            # Click the "Laporan Keuangan" tab if needed
            tab_selector = "a[href*='laporan-keuangan'], button:has-text('Laporan Keuangan')"
            tabs = page.query_selector_all("a, button")
            for tab in tabs:
                if "laporan" in tab.inner_text().lower() and "keuangan" in tab.inner_text().lower():
                    tab.click()
                    page.wait_for_timeout(500)
                    break

            # Get the dropdown list - look for elements containing the monthly reports
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Find the dropdown or list containing report links
            day = MONTH_DAYS[month]
            target_text = f"LAPORAN KEUANGAN BULANAN PER {day:02d} {MONTH_NAMES[month]} {year}"

            # Look for any link or button containing the target month report
            candidates = []
            for element in soup.find_all(['a', 'button', 'div']):
                text = element.get_text(strip=True)
                if MONTH_NAMES[month] in text and str(year) in text and "LAPORAN KEUANGAN" in text:
                    # Try to extract href or onclick
                    href = element.get("href")
                    if href and href.startswith("http"):
                        candidates.append(href)
                    elif href and not href.startswith("http"):
                        candidates.append(f"https://indolife.co.id{href}")

            if candidates:
                return candidates[0]

            # Fallback: Try clicking on elements in the dropdown to trigger navigation
            for element in soup.find_all(['a', 'button', 'li']):
                text = element.get_text(strip=True)
                if MONTH_NAMES[month] in text and str(year) in text:
                    # Try to find the link within or near this element
                    link = element.find('a', href=True)
                    if link and link.get('href'):
                        href = link.get('href')
                        if href.startswith("http"):
                            return href
                        else:
                            return f"https://indolife.co.id{href}"

            return None

        finally:
            browser.close()

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
    
    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"
    
    LOGGER.info(f"Fetching from {SOURCE_URL}")
    
    try:
        if args.use_browser:
            LOGGER.info("Using Playwright browser rendering")
            html, discovered_url = fetch_html_browser(SOURCE_URL, args.timeout)
        else:
            html, discovered_url, used_browser = fetch_html_with_smart_fallback(
                session, SOURCE_URL, args.year, args.month, args.timeout
            )
    except Exception as e:
        reason = f"failed to fetch: {e}"
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
    
    candidates = extract_pdf_links(html, discovered_url, args.year, args.month)
    
    if not candidates:
        reason = "no PDF candidates found"
        LOGGER.warning(reason)
        if args.debug_html:
            write_debug_html(debug_dir, html, reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1
    
    selected_candidate = candidates[0]
    LOGGER.info(f"Selected: {selected_candidate.text[:60]}")
    
    if args.discover_only:
        LOGGER.info("Discover-only mode: stopping after discovery")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discover-only mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {selected_candidate.url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0
    
    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0
    
    http_status, file_size = download_pdf(
        session, selected_candidate.url, output_pdf, timeout=args.timeout, force=args.force
    )
    
    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": "downloaded" if success else "failed",
        "reason": reason, "timestamp": current_timestamp()
    }])
    
    if success:
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
    else:
        LOGGER.error(f"Failed to download: {reason}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
