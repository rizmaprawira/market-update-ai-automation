"""Download financial reports for PT Asuransi Intra Asia."""
import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, discover_download_candidate, current_timestamp, PDFCandidate
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_asuransi_intra_asia")
SOURCE_URL = "https://intraasia.id/id/gcg"
COMPANY_ID = "pt_asuransi_intra_asia"
COMPANY_NAME = "PT Asuransi Intra Asia"
CATEGORY = "asuransi_umum"

def discover_from_embedded_json(html, year, month, timeout=30):
    """Extract PDF URL from embedded JSON in select option data-url attributes."""
    month_names_id = {
        1: "januari", 2: "februari", 3: "maret", 4: "april",
        5: "mei", 6: "juni", 7: "juli", 8: "agustus",
        9: "september", 10: "oktober", 11: "november", 12: "desember"
    }
    month_name = month_names_id[month]

    soup = BeautifulSoup(html, "html.parser")
    year_select = soup.find("select", {"id": "quarterly-year"})

    if not year_select:
        raise Exception("Could not find year select element")

    year_option = year_select.find("option", {"value": str(year)})
    if not year_option:
        raise Exception(f"Year {year} not found in options")

    data_url_str = year_option.get("data-url", "")
    if not data_url_str:
        raise Exception(f"No data-url found for year {year}")

    try:
        data = json.loads(data_url_str)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON from data-url: {e}")

    for item in data:
        quartal = item.get("quartal", "").lower()
        href = item.get("href", "")
        if month_name in quartal and ".pdf" in href.lower():
            full_url = href if href.startswith("http") else urljoin(SOURCE_URL, href)
            return {"url": full_url, "text": f"{item.get('quartal', 'Report')}"}

    raise Exception(f"No PDF found for month {month_name} in year {year} data")

def discover_via_browser_interaction(year, month, timeout=30):
    """Use Playwright to interact with the interactive website and find report URLs."""
    if not sync_playwright:
        raise Exception("Playwright not installed")

    month_names_id = {
        1: "januari", 2: "februari", 3: "maret", 4: "april",
        5: "mei", 6: "juni", 7: "juli", 8: "agustus",
        9: "september", 10: "oktober", 11: "november", 12: "desember"
    }

    month_names_en = {
        1: "january", 2: "february", 3: "march", 4: "april",
        5: "may", 6: "june", 7: "july", 8: "august",
        9: "september", 10: "october", 11: "november", 12: "december"
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(SOURCE_URL, wait_until="load", timeout=timeout*1000)

            time.sleep(3)
            page.wait_for_load_state("networkidle", timeout=10*1000)

            year_text = str(year)
            month_id = month_names_id[month]
            month_en = month_names_en[month]

            found_report = False

            year_selectors = [
                f"select[name*='tahun'] option:has-text('{year_text}')",
                f"button:has-text('{year_text}')",
                f"div[class*='dropdown'] >> button:has-text('{year_text}')",
                f"select option:has-text('{year_text}')",
            ]

            for selector in year_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        page.click(selector, force=True)
                        page.wait_for_load_state("networkidle", timeout=10*1000)
                        break
                except Exception as e:
                    LOGGER.debug(f"Year selector {selector} failed: {e}")

            month_selectors = [
                f"select[name*='bulan'] option:has-text('{month_id}')",
                f"button:has-text('{month_id}')",
                f"div[class*='dropdown'] >> button:has-text('{month_id}')",
                f"select option:has-text('{month_id}')",
            ]

            for selector in month_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        page.click(selector, force=True)
                        page.wait_for_load_state("networkidle", timeout=10*1000)
                        found_report = True
                        break
                except Exception as e:
                    LOGGER.debug(f"Month selector {selector} failed: {e}")

            time.sleep(2)
            content = page.content()

            soup = BeautifulSoup(content, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if ".pdf" in href.lower():
                    full_url = href if href.startswith("http") else urljoin(SOURCE_URL, href)
                    browser.close()
                    return {"url": full_url, "text": text[:60] if text else "Report"}

            browser.close()
            raise Exception("No PDF links found after browser interaction")

    except Exception as e:
        raise Exception(f"Browser interaction failed: {e}")

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Download validation without writing file")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
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

    try:
        LOGGER.info("Using Playwright browser rendering (site is interactive)")
        html, discovered_url = fetch_html_browser(SOURCE_URL, args.timeout)
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
        try:
            candidate = discover_from_embedded_json(html, args.year, args.month, timeout=args.timeout)
            candidates = [PDFCandidate(url=candidate["url"], text=candidate["text"], score=85, discovered_url=SOURCE_URL)]
            LOGGER.info(f"Discovered candidate from embedded JSON data: {candidate['url']}")
        except Exception as e:
            LOGGER.debug(f"Embedded JSON discovery failed: {e}")

    if not candidates:
        try:
            fallback = discover_download_candidate(
                session, html, discovered_url, args.year, args.month, timeout=args.timeout
            )
            candidates = [fallback]
            LOGGER.info(f"Discovered candidate via multi-hop fallback: {fallback.url}")
        except Exception:
            pass

    if not candidates:
        try:
            candidate = discover_via_browser_interaction(args.year, args.month, timeout=args.timeout)
            candidates = [PDFCandidate(url=candidate["url"], text=candidate["text"], score=75, discovered_url=SOURCE_URL)]
            LOGGER.info(f"Discovered candidate via browser interaction: {candidate['url']}")
        except Exception as e:
            LOGGER.debug(f"Browser interaction discovery failed: {e}")

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
        reason = "discovery completed; download skipped by --discover-only"
        LOGGER.info(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": reason,
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
    
    try:
        http_status, file_size = download_pdf(
            session, selected_candidate.url, output_pdf, timeout=args.timeout, force=args.force
        )
        success = True
        reason = (
            f"downloaded conventional financial report PDF (http_status={http_status}, bytes={file_size})"
            if http_status is not None
            else f"existing valid PDF was kept (bytes={file_size})"
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
    except Exception as e:
        success = False
        reason = f"failed to download PDF: {e}"
        status = "error"

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status,
        "reason": reason, "timestamp": current_timestamp()
    }])
    
    if success:
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
    else:
        LOGGER.error(f"Failed to download: {reason}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
