"""Download financial reports for PT Asuransi Jiwa Manulife Indonesia."""
import argparse
import logging
import sys
import requests
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

LOGGER = logging.getLogger("download_pt_asuransi_jiwa_manulife_indonesia")
SOURCE_URL = "https://www.manulife.co.id/id/tentang-kami/laporan-keuangan.html"
COMPANY_ID = "pt_asuransi_jiwa_manulife_indonesia"
COMPANY_NAME = "PT Asuransi Jiwa Manulife Indonesia"
CATEGORY = "asuransi_jiwa"

def download_pdf_via_playwright(pdf_url, output_path, timeout=30):
    """Download PDF using Playwright to bypass 403 blocking."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
        """)

        try:
            # Load source page to establish session
            page.goto(SOURCE_URL, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # Use Playwright's fetch API to download PDF with session cookies
            response = page.context.request.get(pdf_url, timeout=timeout*1000)
            if response.status >= 400:
                LOGGER.error(f"PDF URL returned error status {response.status}")
                return False

            content = response.body()

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

def build_manulife_pdf_url(year, month):
    """Build direct URL to Manulife monthly financial report PDF."""
    # Map month number to Indonesian month names as used in URL
    month_names_id = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }

    month_id = month_names_id.get(month, month_name[month])
    # URL encode spaces as %20
    pdf_filename = f"Laporan%20Keuangan%20Publikasi%20Konvensional%20{month_id}%20{year}.pdf"
    return f"https://www.manulife.co.id/content/dam/insurance/id/documents/laporan-keuangan/laporan-keuangan-bulanan-konvensional/{year}/{pdf_filename}"

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
    
    # Build direct URL to Manulife monthly report PDF
    pdf_url = build_manulife_pdf_url(args.year, args.month)
    LOGGER.info(f"Built PDF URL: {pdf_url}")
    discovered_url = SOURCE_URL

    # Create a simple candidate object
    class Candidate:
        def __init__(self, url):
            self.url = url
            self.text = "PDF (built URL)"

    candidates = [Candidate(pdf_url)]

    # Validate URL exists with a HEAD request
    try:
        resp = session.head(pdf_url, timeout=args.timeout, allow_redirects=True)
        if resp.status_code != 200:
            LOGGER.warning(f"PDF URL returned status {resp.status_code}, trying anyway...")
    except Exception as e:
        LOGGER.warning(f"Could not validate PDF URL: {e}")

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
    
    # Download via Playwright to bypass 403 blocking
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
