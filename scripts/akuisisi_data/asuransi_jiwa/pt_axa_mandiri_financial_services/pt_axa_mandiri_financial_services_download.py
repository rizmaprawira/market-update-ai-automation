"""Download financial reports for PT AXA Mandiri Financial Services."""
import argparse
import logging
import sys
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, download_pdf, write_manifest,
    fetch_html_with_smart_fallback, current_timestamp, MONTH_NAMES
)

LOGGER = logging.getLogger("download_pt_axa_mandiri_financial_services")
SOURCE_URL = "https://www.axa-mandiri.co.id/laporan-keuangan-detail"
COMPANY_ID = "pt_axa_mandiri_financial_services"
COMPANY_NAME = "PT AXA Mandiri Financial Services"
CATEGORY = "asuransi_jiwa"

def extract_axa_mandiri_pdfs(html, base_url, year, month):
    """Custom extraction for AXA Mandiri with strict month/year validation."""
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []

    # Get month names for strict matching
    month_names = MONTH_NAMES.get(month, [])
    month_names_lower = [m.lower() for m in month_names]

    for link in soup.find_all('a'):
        href = link.get('href', '').strip()
        if not href or not href.lower().endswith('.pdf'):
            continue

        text = link.get_text(strip=True).lower()
        url = urljoin(base_url, href)
        full_text = (text + " " + url.lower()).lower()

        # Strict month matching: must contain full month name, not just a digit
        has_month = any(month_name in full_text for month_name in month_names_lower)
        has_year = str(year) in full_text

        # Must match BOTH month and year explicitly
        if has_month and has_year:
            score = 100
            candidates.append({
                'url': url,
                'text': link.get_text(strip=True),
                'score': score
            })

    return sorted(candidates, key=lambda x: x['score'], reverse=True)

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

    if not args.year or not args.month or not (1 <= args.month <= 12):
        LOGGER.error("Year and month (1-12) are required")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    LOGGER.info(f"Discovering PDF for {period}")

    try:
        html, discovered_url, used_browser = fetch_html_with_smart_fallback(
            session, SOURCE_URL, args.year, args.month, args.timeout
        )
        candidates = extract_axa_mandiri_pdfs(html, discovered_url, args.year, args.month)

        if not candidates:
            reason = "no PDF candidates found"
            LOGGER.warning(reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
                "pdf_url": "", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "not_found", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 1

        pdf_url = candidates[0]['url']
        LOGGER.info(f"Found: {candidates[0]['text'][:60]}")

    except Exception as e:
        reason = f"failed to fetch: {e}"
        LOGGER.error(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "error", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

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

    try:
        http_status, file_size = download_pdf(
            session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
        reason = (
            f"HTTP {http_status} ({file_size} bytes)"
            if http_status is not None
            else f"existing valid PDF kept ({file_size} bytes)"
        )
    except Exception as e:
        LOGGER.warning(f"Direct download failed ({e}), trying Playwright fetch")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                response = page.goto(pdf_url, timeout=args.timeout * 1000, wait_until="commit")
                page.wait_for_timeout(2000)
                pdf_bytes = page.pdf()
                output_pdf.parent.mkdir(parents=True, exist_ok=True)
                output_pdf.write_bytes(pdf_bytes)
                file_size = len(pdf_bytes)
                browser.close()
                status = "downloaded"
                reason = f"Playwright PDF export ({file_size} bytes)"
                http_status = 200
        except Exception as e2:
            LOGGER.error(f"Playwright fetch failed: {e2}")
            status = "error"
            reason = f"Failed to download via HTTP and Playwright: {e2}"
            http_status = None
            file_size = 0

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if http_status is not None and status == "downloaded":
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
    elif status == "skipped_existing":
        LOGGER.info(f"PDF already exists, keeping cached version")
    else:
        LOGGER.error(f"Failed to download: {reason}")

    return 0 if status in ["downloaded", "skipped_existing"] else 1

if __name__ == "__main__":
    sys.exit(main())
