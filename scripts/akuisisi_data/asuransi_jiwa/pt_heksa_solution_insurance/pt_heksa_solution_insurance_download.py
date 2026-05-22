"""Download financial reports for PT Heksa Solution Insurance."""
import argparse
import logging
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp
)

LOGGER = logging.getLogger("download_pt_heksa_solution_insurance")
SOURCE_URL = "https://www.heksainsurance.co.id/about/companyreport"
COMPANY_ID = "pt_heksa_solution_insurance"
COMPANY_NAME = "PT Heksa Solution Insurance"
CATEGORY = "asuransi_jiwa"

MONTH_LABELS = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def convert_google_drive_url(view_url: str) -> str:
    """Convert Google Drive view URL to direct download URL."""
    import re
    match = re.search(r'/file/d/([^/]+)/', view_url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return view_url

def discover_heksa_report(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL from Heksa accordion menu using Playwright."""
    month_name = MONTH_LABELS[month]
    target_text = f"{month_name} {year}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Scroll to reveal content
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(300)

            # Get page HTML to find accordion and links
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Find the accordion section containing the target year
            # Look for button text like "Laporan bulanan tahun 2026"
            buttons = soup.find_all("button", {"class": "accordion-button"})
            LOGGER.info(f"Found {len(buttons)} accordion buttons")

            for button in buttons:
                button_text = button.get_text(strip=True)
                if str(year) in button_text:
                    LOGGER.info(f"Found accordion for year {year}: {button_text}")

                    # Find the parent accordion item
                    accordion_item = button.find_parent("div", {"class": "accordion-item"})
                    if not accordion_item:
                        continue

                    # Find the list of reports in this accordion section
                    report_list = accordion_item.find("ul", {"class": "list-check-blue"})
                    if not report_list:
                        continue

                    # Find the list item containing the target month
                    list_items = report_list.find_all("li")
                    for li in list_items:
                        li_text = li.get_text(strip=True)
                        if target_text.lower() in li_text.lower():
                            # Find the download link in this list item
                            link = li.find("a", {"class": "download-file"})
                            if link:
                                href = link.get("href", "").strip()
                                if href:
                                    # Convert Google Drive view URL to download URL if needed
                                    if "drive.google.com" in href:
                                        href = convert_google_drive_url(href)
                                    LOGGER.info(f"Found {target_text}: {href}")
                                    browser.close()
                                    return href

            # Alternative: find any link containing the target month and year
            LOGGER.info(f"Accordion search failed, trying direct link search for '{target_text}'")
            for link in soup.find_all("a", {"class": "download-file"}):
                parent_li = link.find_parent("li")
                if parent_li:
                    li_text = parent_li.get_text(strip=True)
                    if target_text.lower() in li_text.lower():
                        href = link.get("href", "").strip()
                        if href:
                            # Convert Google Drive view URL to download URL if needed
                            if "drive.google.com" in href:
                                href = convert_google_drive_url(href)
                            LOGGER.info(f"Found via direct search: {href}")
                            browser.close()
                            return href

            LOGGER.warning(f"Could not find download link for {target_text}")
            browser.close()
            return None
    except Exception as e:
        LOGGER.error(f"Error discovering Heksa report: {e}")
        import traceback
        LOGGER.error(traceback.format_exc())
        return None

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Validation only, no download")
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

    # Use site-specific discovery for Heksa dropdown menu
    pdf_url = discover_heksa_report(args.year, args.month, args.timeout)

    if not pdf_url:
        reason = "no PDF found in dropdown menu"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Selected: {pdf_url}")

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
    else:
        LOGGER.info(f"File handling: {reason}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
