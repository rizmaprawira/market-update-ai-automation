"""Download financial reports for PT Asuransi Jiwa Mandiri Inhealth Indonesia."""
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

LOGGER = logging.getLogger("download_pt_asuransi_jiwa_mandiri_inhealth_indonesia")
SOURCE_URL = "https://www.inhealth.co.id/id/gcg"
COMPANY_ID = "pt_asuransi_jiwa_mandiri_inhealth_indonesia"
COMPANY_NAME = "PT Asuransi Jiwa Mandiri Inhealth Indonesia"
CATEGORY = "asuransi_jiwa"

def fetch_mandiri_inhealth_pdfs(year, month, timeout=30):
    """Fetch Mandiri InHealth monthly PDF using JSON data extraction."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout * 1000)

            # Wait for the financial reports section to load
            # The page loads data via JavaScript, so we need to wait for it
            try:
                page.wait_for_function(
                    'document.documentElement.innerHTML.includes("Bulanan")',
                    timeout=timeout * 1000
                )
                LOGGER.debug("Found Bulanan section in rendered page")
            except Exception as e:
                LOGGER.warning(f"Timeout waiting for Bulanan section: {e}")

            # Additional wait for content to settle
            page.wait_for_timeout(2000)

            # Get page content
            content = page.content()

            # Extract monthly reports from the embedded JSON data
            import re

            # The page has heavily escaped JSON data. Look for fileUrl entries with "bulanan"
            # Pattern: \"fileUrl\":\"laporan_keuangan_mandiri_inhealth_bulanan_[month]_[year]_*.pdf\"

            # Build month name
            month_name_id = month_name[month].lower()
            target_month_indo = {
                'january': 'januari', 'february': 'februari', 'march': 'maret',
                'april': 'april', 'may': 'mei', 'june': 'juni',
                'july': 'juli', 'august': 'agustus', 'september': 'september',
                'october': 'oktober', 'november': 'november', 'december': 'desember'
            }.get(month_name_id, month_name_id)

            LOGGER.info(f"Looking for monthly report: {target_month_indo} {year}")

            # Search for fileUrl with bulanan keyword and matching month/year
            # Handle both escaped and unescaped versions
            pattern = rf'fileUrl[\\]*["\:]*[\\]*["\:]*laporan_keuangan_mandiri_inhealth_bulanan[^"\\]*?{target_month_indo}[^"\\]*?{year}[^"\\]*?\.pdf'
            matches = re.finditer(pattern, content, re.IGNORECASE)

            matching_pdfs = []
            seen = set()

            for match in matches:
                # Extract just the filename from the match
                full_match = match.group(0)
                # Extract PDF filename (after the last / or the actual filename)
                filename_match = re.search(r'(laporan_keuangan[^"\\]*\.pdf)', full_match, re.IGNORECASE)
                if filename_match:
                    filename = filename_match.group(1)
                    if filename not in seen:
                        seen.add(filename)
                        LOGGER.info(f"Found matching monthly report: {filename}")
                        # Construct full URL
                        pdf_url = f"https://www.inhealth.co.id/api/cms/preview/{filename}"
                        matching_pdfs.append(pdf_url)

            if matching_pdfs:
                LOGGER.info(f"Found {len(matching_pdfs)} matching monthly PDFs")
            else:
                LOGGER.warning(f"No monthly reports found for {target_month_indo} {year}")
                # Try a simpler pattern if the first didn't work
                simple_pattern = rf'bulanan[^"\\]*{target_month_indo}[^"\\]*{year}[^"\\]*\.pdf'
                simple_matches = re.finditer(simple_pattern, content, re.IGNORECASE)
                for match in simple_matches:
                    filename = match.group(0)
                    if filename not in seen and 'bulanan' in filename.lower():
                        seen.add(filename)
                        LOGGER.info(f"Found via simpler pattern: {filename}")
                        pdf_url = f"https://www.inhealth.co.id/api/cms/preview/{filename}"
                        matching_pdfs.append(pdf_url)

            return content, SOURCE_URL, matching_pdfs if matching_pdfs else []

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
        # Use Playwright to handle popup and dropdown interaction
        LOGGER.info("Using Playwright with popup close + dropdown selection")
        html, discovered_url, pdf_urls = fetch_mandiri_inhealth_pdfs(args.year, args.month, args.timeout)

        # Create candidate objects from extracted URLs
        if pdf_urls:
            class Candidate:
                def __init__(self, url):
                    self.url = url
                    self.text = "PDF (extracted)"
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

    try:
        http_status, file_size = download_pdf(
            session, selected_candidate.url, output_pdf, timeout=args.timeout, force=args.force
        )

        if http_status is not None:
            status = "downloaded"
            reason = f"HTTP {http_status} ({file_size} bytes)"
            LOGGER.info(f"Successfully downloaded to {output_pdf}")
            success = True
        else:
            status = "skipped_existing"
            reason = f"existing valid PDF kept ({file_size} bytes)"
            LOGGER.info(f"PDF already exists and is valid: {output_pdf}")
            success = True
    except Exception as e:
        status = "error"
        reason = f"Failed to download: {e}"
        LOGGER.error(reason)
        success = False

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
