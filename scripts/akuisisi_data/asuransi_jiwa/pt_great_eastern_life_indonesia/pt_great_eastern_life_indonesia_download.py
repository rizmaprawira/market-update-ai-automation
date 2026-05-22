"""Download financial reports for PT Great Eastern Life Indonesia."""
import argparse
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp,
    MONTH_LABELS, sync_playwright
)

LOGGER = logging.getLogger("download_pt_great_eastern_life_indonesia")
SOURCE_URL = "https://www.greateasternlife.com/id/in/tentang-kami/pusat-media/laporan-tahunan.html"
COMPANY_ID = "pt_great_eastern_life_indonesia"
COMPANY_NAME = "PT Great Eastern Life Indonesia"
CATEGORY = "asuransi_jiwa"

def discover_great_eastern_report(year, month, timeout=30):
    """Discover Great Eastern report by scrolling and extracting with strict period filtering."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(2000)

            # Scroll to bottom to reveal "Laporan Keuangan Lainnya" section
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)

            # Get rendered HTML after scrolling
            html = page.content()

            # Extract all PDF candidates (not filtered by period yet)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            month_label = MONTH_LABELS[month].lower()
            year_str = str(year)

            # Find all PDF links and filter by exact period match
            best_match = None
            best_score = -1

            for link in soup.find_all("a"):
                href = link.get("href", "").strip()
                text = link.get_text(strip=True).lower()

                if not href or not href.lower().endswith(".pdf"):
                    continue

                # Score based on period match
                score = 0

                # Check if target year appears in link
                if year_str in text or year_str in href:
                    score += 10

                # Check if target month appears in link (exact match)
                if month_label in text:
                    score += 20
                elif f"0{month}" in text or f"-{month:02d}" in text:
                    score += 15

                # Check for "konvensional" (conventional reports, not syariah)
                if "konvensional" in text or "konvensional" in href.lower():
                    score += 5

                # Only consider if we found a relevant match
                if score > 0 and score > best_score:
                    best_score = score
                    best_match = urljoin(SOURCE_URL, href)

            return best_match
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

    # For Great Eastern, try site-specific discovery to ensure exact period match
    try:
        LOGGER.info("Trying site-specific discovery for Great Eastern period matching")
        pdf_url = discover_great_eastern_report(args.year, args.month, args.timeout)
        if pdf_url:
            from _downloader_base import PDFCandidate
            month_name = MONTH_LABELS[args.month]
            candidates = [PDFCandidate(url=pdf_url, text=f"Laporan Keuangan Konvensional {month_name} {args.year}", score=100, discovered_url=SOURCE_URL)]
            LOGGER.info(f"Site-specific discovery found: {pdf_url}")
    except Exception as e:
        LOGGER.warning(f"Site-specific discovery failed: {e}")

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

    status = "downloaded" if http_status is not None else "skipped_existing"
    reason = (
        f"HTTP {http_status} ({file_size} bytes)"
        if http_status is not None
        else f"existing valid PDF kept ({file_size} bytes)"
    )

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    LOGGER.info(f"Download complete: {status} - {reason}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
