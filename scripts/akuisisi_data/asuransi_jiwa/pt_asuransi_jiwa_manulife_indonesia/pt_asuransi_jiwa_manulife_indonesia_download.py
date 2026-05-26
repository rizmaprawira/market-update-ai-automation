"""Download financial reports for PT Asuransi Jiwa Manulife Indonesia."""
import argparse
import logging
import sys
import requests
import re
from pathlib import Path
from calendar import month_name
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

LOGGER = logging.getLogger("download_pt_asuransi_jiwa_manulife_indonesia")
SOURCE_URL = "https://www.manulife.co.id/id/tentang-kami/laporan-keuangan.html"
COMPANY_ID = "pt_asuransi_jiwa_manulife_indonesia"
COMPANY_NAME = "PT Asuransi Jiwa Manulife Indonesia"
CATEGORY = "asuransi_jiwa"

def find_manulife_pdf_from_archive(year, month):
    """Find Manulife PDF URL from archive.org (fallback for Akamai WAF blocks)."""
    try:
        month_names_id = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
            5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
            9: "September", 10: "Oktober", 11: "November", 12: "Desember"
        }
        target_month = month_names_id.get(month)
        target_year = str(year)

        LOGGER.info("Trying Archive.org as fallback (main site blocked by Akamai WAF)...")

        # Get latest snapshot info from archive.org
        api_url = "https://web.archive.org/web/timemap/json?url=manulife.co.id/id/tentang-kami/laporan-keuangan.html"
        r = requests.get(api_url, timeout=10)

        if r.status_code != 200:
            LOGGER.warning("Could not access Archive.org API")
            return None

        snapshots = r.json()
        if len(snapshots) < 2:
            LOGGER.warning("No Archive.org snapshots available")
            return None

        # Try most recent snapshot
        latest_timestamp = snapshots[-1][1]
        LOGGER.info(f"Trying Archive.org snapshot from {latest_timestamp}")

        snapshot_url = f"https://web.archive.org/web/{latest_timestamp}/manulife.co.id/id/tentang-kami/laporan-keuangan.html"
        r = requests.get(snapshot_url, timeout=15)

        if r.status_code != 200:
            LOGGER.warning(f"Archive snapshot returned {r.status_code}")
            return None

        # Extract PDF paths
        pdf_pattern = r'(/content/dam/insurance/id/documents/[^"\'<>\s]*bulanan-konvensional[^"\'<>\s]*\.pdf)'
        pdf_paths = list(set(re.findall(pdf_pattern, r.text)))

        LOGGER.info(f"Found {len(pdf_paths)} monthly conventional PDFs in archive")

        # Find matching month/year
        for pdf_path in pdf_paths:
            path_lower = pdf_path.lower()
            if target_month.lower() in path_lower and target_year in path_lower:
                archive_url = f"https://web.archive.org/web/{latest_timestamp}/manulife.co.id{pdf_path}"
                LOGGER.info(f"Found matching PDF in archive: {pdf_path[-50:]}")
                return archive_url

        LOGGER.warning(f"No matching PDF found for {target_month} {target_year} in archive")
        if pdf_paths:
            LOGGER.info(f"Available: {pdf_paths[0][-60:]}")
        return None

    except Exception as e:
        LOGGER.warning(f"Archive.org lookup failed: {e}")
        return None

def download_pdf_via_requests(pdf_url, output_path, timeout=30):
    """Download PDF via requests library (best for Archive.org)."""
    try:
        LOGGER.info(f"Downloading PDF via requests: {pdf_url[:80]}...")
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        response = session.get(pdf_url, timeout=timeout, allow_redirects=True)

        if response.status_code >= 400:
            LOGGER.error(f"PDF URL returned error status {response.status_code}")
            return False

        content = response.content

        # Verify we got a PDF, not an error page
        if not content.startswith(b'%PDF'):
            LOGGER.error(f"Downloaded content is not a valid PDF (got {len(content)} bytes, first bytes: {content[:20]})")
            return False

        # Write PDF to file
        with open(output_path, 'wb') as f:
            f.write(content)

        LOGGER.info(f"Downloaded valid PDF ({len(content)} bytes) to {output_path}")
        return True
    except Exception as e:
        LOGGER.error(f"Failed to download via requests: {e}")
        return False

def download_pdf_via_cloudscraper(pdf_url, output_path, timeout=30):
    """Download PDF using cloudscraper to bypass Akamai WAF."""
    if cloudscraper is None:
        LOGGER.warning("cloudscraper not available, falling back to other methods")
        return False

    try:
        scraper = cloudscraper.create_scraper()
        LOGGER.info(f"Downloading PDF via cloudscraper: {pdf_url[:80]}...")
        response = scraper.get(pdf_url, timeout=timeout)

        if response.status_code >= 400:
            LOGGER.error(f"PDF URL returned error status {response.status_code}")
            return False

        content = response.content

        # Verify we got a PDF, not an error page
        if not content.startswith(b'%PDF'):
            LOGGER.error(f"Downloaded content is not a valid PDF (got {len(content)} bytes)")
            return False

        # Write PDF to file
        with open(output_path, 'wb') as f:
            f.write(content)

        LOGGER.info(f"Downloaded valid PDF ({len(content)} bytes) to {output_path}")
        return True
    except Exception as e:
        LOGGER.error(f"Failed to download via cloudscraper: {e}")
        return False

def download_pdf_via_playwright(pdf_url, output_path, timeout=30):
    """Download PDF using Playwright to bypass 403 blocking."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
        """)

        try:
            # Set default timeout for all operations
            page.set_default_timeout(timeout * 1000)

            # Load source page to establish session and cookies
            LOGGER.info("Loading source page to establish session...")
            page.goto(SOURCE_URL, timeout=15000, wait_until="networkidle")
            page.wait_for_timeout(2000)

            # Use JavaScript fetch API within page context to download PDF with all cookies/headers
            LOGGER.info(f"Downloading PDF via fetch from within page context: {pdf_url}")
            pdf_data = page.evaluate(f"""
                async () => {{
                    const response = await fetch('{pdf_url}', {{
                        method: 'GET',
                        credentials: 'include',
                        headers: {{
                            'Referer': '{SOURCE_URL}'
                        }}
                    }});
                    if (!response.ok) {{
                        throw new Error(`HTTP error! status: ${{response.status}}`);
                    }}
                    const blob = await response.blob();
                    const reader = new FileReader();
                    return new Promise((resolve) => {{
                        reader.onloadend = () => {{
                            resolve(Array.from(new Uint8Array(reader.result)));
                        }};
                        reader.readAsArrayBuffer(blob);
                    }});
                }}
            """)

            # Convert list of bytes to bytes object
            content = bytes(pdf_data)

            # Verify we got a PDF, not an error page
            if not content.startswith(b'%PDF'):
                LOGGER.error(f"Downloaded content is not a valid PDF (got {len(content)} bytes, first bytes: {content[:20]})")
                return False

            # Write PDF to file
            with open(output_path, 'wb') as f:
                f.write(content)

            LOGGER.info(f"Downloaded valid PDF ({len(content)} bytes) to {output_path}")
            return True
        except Exception as e:
            LOGGER.error(f"Failed to download via Playwright: {e}")
            return False
        finally:
            context.close()
            browser.close()

def find_manulife_pdf_url(year, month):
    """Find Manulife monthly financial report PDF link by scraping the website."""
    month_names_id = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }

    target_month = month_names_id.get(month)
    target_year = str(year)

    # Try cloudscraper first
    if cloudscraper is not None:
        try:
            LOGGER.info(f"Attempting to access Manulife website for {target_month} {target_year} via cloudscraper...")
            scraper = cloudscraper.create_scraper()
            response = scraper.get(SOURCE_URL, timeout=30)

            if response.status_code >= 400:
                LOGGER.warning(f"Website returned status {response.status_code}, trying Playwright...")
            else:
                LOGGER.info(f"Successfully accessed website via cloudscraper")
                # Parse HTML to find PDF links
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                pdf_links = []
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if href.endswith('.pdf') or 'laporan' in text.lower():
                        pdf_links.append({'text': text, 'href': href})

                # Look for matching link
                for link in pdf_links:
                    link_text_lower = link['text'].lower()
                    if target_month.lower() in link_text_lower and target_year in link_text_lower:
                        LOGGER.info(f"Found matching PDF link: {link['text']}")
                        return link['href']

                if not pdf_links:
                    LOGGER.warning(f"No PDF links found for {target_month} {target_year}")
                else:
                    LOGGER.warning(f"No matching PDF link found for {target_month} {target_year}")
                    LOGGER.info(f"Available links: {pdf_links[:3]}")
        except Exception as e:
            LOGGER.warning(f"cloudscraper failed: {e}, trying Playwright...")

    # Fall back to Playwright
    if sync_playwright is None:
        LOGGER.error("Playwright not available and cloudscraper failed")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            try:
                LOGGER.info(f"Attempting via Playwright...")
                response = page.goto(SOURCE_URL, wait_until="domcontentloaded")

                if response.status == 403:
                    LOGGER.error("Manulife website returns 403 Forbidden")
                    return None

                page.wait_for_timeout(3000)
                return None

            except Exception as e:
                LOGGER.error(f"Error with Playwright: {e}")
                return None
            finally:
                context.close()
                browser.close()

    except Exception as e:
        LOGGER.error(f"Error accessing website: {e}")
        return None

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

    # Find PDF URL by scraping the website
    pdf_url = find_manulife_pdf_url(args.year, args.month)
    discovered_url = SOURCE_URL

    # If main website is blocked, try Archive.org
    if not pdf_url:
        LOGGER.info("Main website inaccessible, trying Archive.org fallback...")
        pdf_url = find_manulife_pdf_from_archive(args.year, args.month)
        if pdf_url:
            discovered_url = "https://web.archive.org (Akamai WAF bypass)"

    # Create a simple candidate object
    class Candidate:
        def __init__(self, url):
            self.url = url
            self.text = "PDF (found via website scraping or archive)"

    candidates = [Candidate(pdf_url)] if pdf_url else []

    if not candidates:
        reason = "PDF not found in website or Archive.org - may not exist for this period"
        LOGGER.warning(reason)
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
    
    # Download PDF - try best method for the source
    try:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        # For Archive.org URLs, use requests directly (faster and more reliable)
        if 'archive.org' in selected_candidate.url:
            success = download_pdf_via_requests(selected_candidate.url, str(output_pdf), args.timeout)
        else:
            # For main website, try cloudscraper first (better for Akamai WAF)
            success = download_pdf_via_cloudscraper(selected_candidate.url, str(output_pdf), args.timeout)

        if not success and 'archive.org' not in selected_candidate.url:
            # Fall back to Playwright for main website
            LOGGER.info("Cloudscraper failed, trying Playwright...")
            success = download_pdf_via_playwright(selected_candidate.url, str(output_pdf), args.timeout)

        if success and output_pdf.exists():
            file_size = output_pdf.stat().st_size
            status = "downloaded"
            reason = f"Downloaded successfully ({file_size} bytes)"
            LOGGER.info(f"Successfully downloaded to {output_pdf}")
        else:
            status = "error"
            reason = "Failed to download PDF"
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
