"""Download financial reports for PT Asuransi Staco Mandiri."""
import argparse
import logging
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, download_pdf, write_manifest, write_debug_html,
    fetch_html_with_smart_fallback, current_timestamp, MONTH_NAMES
)

LOGGER = logging.getLogger("download_pt_asuransi_staco_mandiri")
SOURCE_URL = "https://stacoinsurance.com/laporan-bulanan/"
COMPANY_ID = "pt_asuransi_staco_mandiri"
COMPANY_NAME = "PT Asuransi Staco Mandiri"
CATEGORY = "asuransi_umum"

def extract_staco_pdfs(html, base_url, year, month):
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []
    month_names = MONTH_NAMES.get(month, [])
    month_names_lower = [m.lower() for m in month_names]
    for link in soup.find_all('a'):
        href = link.get('href', '').strip()
        if not href or not href.lower().endswith('.pdf'):
            continue
        text = link.get_text(strip=True).lower()
        url = urljoin(base_url, href)
        full_text = (text + " " + url.lower()).lower()
        has_month = any(month_name in full_text for month_name in month_names_lower)
        has_year = str(year) in full_text
        if has_month and has_year:
            candidates.append({'url': url, 'text': link.get_text(strip=True), 'score': 100})
    return sorted(candidates, key=lambda x: x['score'], reverse=True)

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, no download")
    parser.add_argument("--dry-run", action="store_true", help="Validate download without writing")
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

    candidates = extract_staco_pdfs(html, discovered_url, args.year, args.month)

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

    selected = candidates[0]
    LOGGER.info(f"Selected: {selected['text'][:60]}")

    if args.discover_only:
        LOGGER.info("Discovery complete (--discover-only mode)")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discovery complete",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {selected['url']}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    try:
        http_status, file_size = download_pdf(
            session, selected['url'], output_pdf, timeout=args.timeout, force=args.force
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
        reason = f"HTTP {http_status} ({file_size} bytes)" if http_status else f"existing ({file_size} bytes)"
        success = True
    except Exception as e:
        status = "error"
        reason = f"Failed to download: {e}"
        LOGGER.error(reason)
        success = False

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected['url'], "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
