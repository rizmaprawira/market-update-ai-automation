"""Download financial reports for PT Asuransi Allianz Utama Indonesia."""
import argparse
import logging
import sys
import re
from pathlib import Path
from calendar import month_name

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_asuransi_jiwa_ifg")
SOURCE_URL = "https://ifg-life.id/about?propKey=report&subValue=&optional="
COMPANY_ID = "pt_asuransi_jiwa_ifg"
COMPANY_NAME = "PT Asuransi Jiwa IFG"
CATEGORY = "asuransi_jiwa"

def download_pdf_via_playwright(pdf_url, output_path, timeout=30):
    """Download PDF using Playwright session to bypass IFG's 403 blocking."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    import requests

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
        """)

        try:
            # Load a page to establish session/cookies
            page.goto(SOURCE_URL, timeout=timeout * 1000)
            page.wait_for_load_state("networkidle", timeout=timeout * 1000)

            # Get cookies and headers from the session
            cookies = context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

            # Download PDF using requests with session cookies
            response = requests.get(pdf_url, cookies=cookie_dict, headers=headers, timeout=timeout)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)
            LOGGER.info(f"Downloaded {len(response.content)} bytes to {output_path}")
            return True
        except Exception as e:
            LOGGER.error(f"Failed to download: {e}")
            return False
        finally:
            context.close()
            browser.close()

def fetch_ifg_pdfs(year, month, timeout=30):
    """Fetch IFG PDFs using Playwright with anti-bot bypass (headless=False + stealth)."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        # IFG blocks headless browsers, use headless=False
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        # Add stealth to hide playwright
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)

        try:
            page.goto(SOURCE_URL, wait_until="networkidle", timeout=timeout * 1000)
            content = page.content()

            # Extract all PDF URLs from page HTML
            pdf_urls = re.findall(r'https://[^\s"<>]+\.pdf', content)

            # Filter by year and month
            month_keywords = [month_name[month].lower(), str(month).zfill(2), f"0{month}"]
            matching_pdfs = [
                url for url in pdf_urls
                if str(year) in url and any(kw in url.lower() for kw in month_keywords)
            ]

            LOGGER.info(f"Found {len(matching_pdfs)} PDFs for {year}-{month:02d}")

            return content, SOURCE_URL, matching_pdfs if matching_pdfs else pdf_urls
        finally:
            browser.close()

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

    try:
        # IFG requires special handling: anti-bot bypass with headless=False
        LOGGER.info("Using Playwright with anti-bot bypass (headless=False)")
        html, discovered_url, pdf_urls = fetch_ifg_pdfs(args.year, args.month, args.timeout)

        # Use the first matching PDF URL as candidate
        if pdf_urls:
            # Create a simple candidate object
            class Candidate:
                def __init__(self, url):
                    self.url = url
                    self.text = "PDF (extracted from page)"
            candidates = [Candidate(pdf_urls[0])]
        else:
            candidates = []
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
    
    # For IFG, download via Playwright to bypass 403
    try:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        success = download_pdf_via_playwright(selected_candidate.url, str(output_pdf), args.timeout)

        if success and output_pdf.exists():
            file_size = output_pdf.stat().st_size
            status = "downloaded"
            reason = f"Downloaded via Playwright ({file_size} bytes)"
            LOGGER.info(f"Successfully downloaded to {output_pdf}")
        else:
            status = "error"
            reason = "Failed to download PDF via Playwright"
            success = False
    except Exception as e:
        status = "error"
        reason = f"Download error: {e}"
        success = False
        LOGGER.error(reason)

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
