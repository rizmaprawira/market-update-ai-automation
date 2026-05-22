"""Download financial reports for PT Asuransi Allianz Life Indonesia."""
import argparse
import logging
import sys
import time
import json
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp
)

LOGGER = logging.getLogger("download_pt_asuransi_allianz_life_indonesia")
SOURCE_URL = "https://www.allianz.co.id/tentang-kami/finansial.html"
COMPANY_ID = "pt_asuransi_allianz_life_indonesia"
COMPANY_NAME = "PT Asuransi Allianz Life Indonesia"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def discover_allianz_life_pdf(year: int, month: int, timeout: int = 30) -> str:
    """Discover PDF URL from Allianz Life dropdown + list."""
    month_name = MONTH_NAMES[month]
    target_text = f"Laporan Keuangan Bulan {month_name} {year}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Scroll down to reveal Laporan Keuangan section
            for _ in range(8):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(300)

            page.wait_for_timeout(1500)

            # Get rendered HTML and parse it
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Find all PDF links on the page and match the exact target month
            best_match = None
            best_score = -1

            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                link_text = link.get_text(strip=True)

                # Check if it's a PDF link
                if not (".pdf" in href.lower() or ".PDF" in href):
                    continue

                score = 0

                # Exact month match
                if month_name.lower() in link_text.lower():
                    score += 20

                # Year match
                if str(year) in link_text:
                    score += 10

                # "Laporan" keyword
                if "laporan" in link_text.lower():
                    score += 5

                # "Keuangan" keyword
                if "keuangan" in link_text.lower():
                    score += 5

                # Bonus for Allianz Life specific
                if "allianz" in link_text.lower() or "life" in link_text.lower():
                    score += 5

                # Penalize non-target months
                for other_month in MONTH_NAMES.values():
                    if other_month != month_name and other_month.lower() in link_text.lower():
                        score -= 20

                if score > best_score:
                    best_score = score
                    best_match = href

            browser.close()

            if best_match:
                # Construct full URL if needed
                if best_match.startswith("http"):
                    return best_match
                elif best_match.startswith("/"):
                    return f"https://www.allianz.co.id{best_match}"
                else:
                    return f"https://www.allianz.co.id/{best_match}"

            return None

    except Exception as e:
        LOGGER.warning(f"Failed to discover via Playwright: {e}")
        return None

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
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF for {args.year}-{args.month:02d}")

    # Try site-specific discovery first
    pdf_url = discover_allianz_life_pdf(args.year, args.month, timeout=args.timeout)

    if not pdf_url:
        # Fallback to generic extraction with Allianz-specific filtering
        LOGGER.info("Falling back to generic extraction with Allianz period filter")
        try:
            html, discovered_url, used_browser = fetch_html_with_smart_fallback(
                session, SOURCE_URL, args.year, args.month, args.timeout
            )
            candidates = extract_pdf_links(html, discovered_url, args.year, args.month)

            # For Allianz, filter to exact month match to avoid period mismatch
            if candidates:
                target_month_name = MONTH_NAMES[args.month]
                # First try to find exact month match
                exact_matches = [
                    c for c in candidates
                    if target_month_name.lower() in c.text.lower() and str(args.year) in c.text
                ]

                if exact_matches:
                    pdf_url = exact_matches[0].url
                    LOGGER.info(f"Found exact month match: {exact_matches[0].text[:60]}")
                else:
                    # Fallback to first candidate if no exact match
                    pdf_url = candidates[0].url
                    LOGGER.info(f"Found via fallback: {candidates[0].text[:60]}")
        except Exception as e:
            LOGGER.warning(f"Generic extraction failed: {e}")
            pdf_url = None

    if not pdf_url:
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

    LOGGER.info(f"Selected PDF: {pdf_url}")

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

    # Try direct HTTP download first
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
        # Fall back to Playwright fetch for 403/blocked URLs
        LOGGER.warning(f"Direct download failed ({e}), trying Playwright fetch")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()

                # Fetch PDF through browser context which sets proper headers
                response = page.goto(pdf_url, timeout=args.timeout * 1000, wait_until="commit")
                page.wait_for_timeout(2000)

                # Get page content as PDF
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
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if http_status is not None and status == "downloaded":
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
        return 0
    elif status == "skipped_existing":
        LOGGER.info(f"File already exists: {output_pdf}")
        return 0
    else:
        LOGGER.error(f"Download failed: {reason}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
