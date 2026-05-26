"""Download financial reports for PT Asuransi Allianz Utama Indonesia."""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, download_pdf, write_manifest, write_debug_html,
    current_timestamp, MONTH_NAMES
)

LOGGER = logging.getLogger("download_pt_asuransi_allianz_utama_indonesia")
SOURCE_URL = "https://www.allianz.co.id/tentang-kami/finansial.html"
COMPANY_ID = "pt_asuransi_allianz_utama_indonesia"
COMPANY_NAME = "PT Asuransi Allianz Utama Indonesia"
CATEGORY = "asuransi_umum"

def download_pdf_via_browser(pdf_url, output_path, timeout=30):
    """Download PDF using Playwright by extracting through the browser context."""
    try:
        import requests
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, 0, "Playwright not installed"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                LOGGER.info(f"Downloading via Playwright context: {pdf_url}")

                # First load the source page to establish cookies/session
                page.goto(SOURCE_URL, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(1000)

                # Get cookies from the browser context
                cookies = context.cookies()

                # Now use requests with browser cookies to download the PDF
                headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
                    'Accept': 'application/pdf, */*',
                    'Referer': SOURCE_URL
                }

                session = requests.Session()
                for cookie in cookies:
                    session.cookies.set(cookie['name'], cookie['value'])

                response = session.get(pdf_url, headers=headers, timeout=timeout, allow_redirects=True)
                response.raise_for_status()

                output_path.write_bytes(response.content)
                file_size = output_path.stat().st_size
                LOGGER.info(f"Downloaded {file_size} bytes via Playwright + requests")
                return True, file_size, f"Downloaded {file_size} bytes"
            finally:
                browser.close()
    except Exception as e:
        LOGGER.error(f"Playwright download failed: {e}")
        return False, 0, f"Playwright download failed: {e}"

def extract_allianz_pdfs_via_browser(year, month):
    """Use Playwright to handle dynamic dropdown and extract PDF links."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        LOGGER.error("Playwright not installed. Install with: pip install playwright")
        return []

    candidates = []
    month_names = MONTH_NAMES.get(month, [])
    month_names_lower = [m.lower() for m in month_names]

    with sync_playwright() as p:
        # Try Firefox first (less likely to be blocked), fallback to chromium
        try:
            LOGGER.info("Launching Firefox browser...")
            browser = p.firefox.launch(headless=True)
        except Exception:
            LOGGER.info("Firefox not available, using Chromium...")
            browser = p.chromium.launch(headless=True)

        page = browser.new_page()
        try:
            LOGGER.info("Loading page...")
            try:
                page.goto(SOURCE_URL, wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                LOGGER.warning(f"Page load timeout: {e}, continuing anyway...")
            page.wait_for_timeout(2000)

            # Scroll down to find "Laporan Keuangan" section
            LOGGER.info("Scrolling to find Laporan Keuangan section...")
            for _ in range(5):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(500)

            # Find the dropdown by looking for buttons/divs containing the text
            dropdown_text = "Laporan Keuangan Allianz Utama Indonesia"
            LOGGER.info(f"Looking for dropdown: {dropdown_text}")

            # Try to find and click the button/div containing the dropdown text
            dropdown_found = False
            try:
                # First try exact match in button or div
                dropdown_buttons = page.locator('button, div[role="button"]').all()
                for btn in dropdown_buttons:
                    text = btn.text_content().strip()
                    if dropdown_text.lower() in text.lower():
                        LOGGER.info(f"Found dropdown button with text: {text}")
                        btn.click()
                        page.wait_for_timeout(1000)
                        dropdown_found = True
                        break

                if not dropdown_found:
                    # Try with get_by_text with shorter timeout
                    dropdown = page.get_by_text(dropdown_text, exact=False)
                    dropdown.click(timeout=5000)
                    page.wait_for_timeout(1000)
                    dropdown_found = True
            except Exception as e:
                LOGGER.debug(f"Could not click dropdown: {e}")

            # Wait for PDF links to appear after expansion
            page.wait_for_timeout(1000)

            # Look for all PDF links on the page
            # Format: "Laporan Keuangan Bulan <Month> <Year>"
            links = page.locator('a[href*=".pdf"], a[href*="PDF"]').all()
            LOGGER.info(f"Found {len(links)} PDF links")

            for link in links:
                try:
                    text = link.text_content().strip()
                    href = link.get_attribute('href')

                    if not href:
                        continue

                    # Check if this looks like a PDF (case-insensitive)
                    if not (href.lower().endswith('.pdf') or '.pdf' in href.lower()):
                        continue

                    # Check if contains target month and year
                    text_lower = text.lower()
                    has_month = any(month_name in text_lower for month_name in month_names_lower)
                    has_year = str(year) in text_lower

                    if has_month and has_year:
                        # Make absolute URL if needed
                        if href.startswith('http'):
                            url = href
                        else:
                            from urllib.parse import urljoin
                            url = urljoin(SOURCE_URL, href)

                        candidates.append({
                            'url': url,
                            'text': text,
                            'score': 100
                        })
                        LOGGER.info(f"Found candidate: {text} -> {url}")
                except Exception as e:
                    LOGGER.debug(f"Error processing link: {e}")
                    continue

        finally:
            browser.close()

    return sorted(candidates, key=lambda x: x['score'], reverse=True)

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no download")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
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
        candidates = extract_allianz_pdfs_via_browser(args.year, args.month)
    except Exception as e:
        reason = f"failed to extract PDFs: {e}"
        LOGGER.error(reason)
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
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    selected = candidates[0]
    LOGGER.info(f"Selected: {selected['text'][:60]}")

    if args.discover_only:
        reason = "discovery completed; download skipped by --discover-only"
        LOGGER.info(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {selected['url']}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    # Download via Playwright to bypass 403 restrictions
    try:
        success, file_size, reason = download_pdf_via_browser(
            selected['url'], output_pdf, args.timeout
        )
        status = "downloaded" if success else "error"
        http_status = 200 if success else None
    except Exception as e:
        success = False
        file_size = 0
        reason = f"Failed to download: {e}"
        status = "error"
        http_status = None

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
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
