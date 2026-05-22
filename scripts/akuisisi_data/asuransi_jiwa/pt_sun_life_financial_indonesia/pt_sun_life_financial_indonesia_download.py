"""Download financial reports for PT Sun Life Financial Indonesia."""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_with_smart_fallback, current_timestamp
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_sun_life_financial_indonesia")
SOURCE_URL = "https://www.sunlife.co.id/id/about-us/who-we-are/financial-report/"
COMPANY_ID = "pt_sun_life_financial_indonesia"
COMPANY_NAME = "PT Sun Life Financial Indonesia"
CATEGORY = "asuransi_jiwa"


def download_sunlife_pdf_browser(pdf_url: str, output_path: Path, timeout: int = 30) -> bool:
    """Download using Playwright to bypass hotlink protection."""
    if sync_playwright is None:
        return False

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            try:
                # Navigate to the PDF link
                page.goto(pdf_url, timeout=timeout * 1000)
                time.sleep(2)

                # Save the page content as PDF
                pdf_bytes = page.pdf()
                output_path.write_bytes(pdf_bytes)
                LOGGER.info(f"Downloaded via browser PDF export: {output_path}")
                return True
            except Exception as e:
                LOGGER.debug(f"Browser PDF export failed: {e}")
                return False
            finally:
                browser.close()
    except Exception as e:
        LOGGER.debug(f"Playwright download failed: {e}")
        return False


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

    if not args.year or not args.month or not 1 <= args.month <= 12:
        LOGGER.error("Year and month (1-12) required")
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

    candidates = extract_pdf_links(html, discovered_url, args.year, args.month)

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
    LOGGER.info(f"Selected: {selected_candidate.text[:80]}")

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

    # Try Playwright PDF export first
    success = download_sunlife_pdf_browser(selected_candidate.url, output_pdf, args.timeout)

    if not success:
        # Fallback to direct HTTP download
        LOGGER.info("Browser export failed, trying direct HTTP")
        try:
            http_status, file_size = download_pdf(
                session, selected_candidate.url, output_pdf, timeout=args.timeout, force=args.force
            )
            success = http_status is not None
            reason = (
                f"HTTP {http_status} ({file_size} bytes)"
                if http_status is not None
                else f"existing valid PDF kept ({file_size} bytes)"
            )
        except Exception as e:
            success = False
            reason = f"download failed: {str(e)[:80]}"
            LOGGER.error(reason)
    else:
        reason = "downloaded via browser (hotlink protected)"

    status = "downloaded" if success else "error"

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if success:
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
        return 0
    else:
        LOGGER.error(f"Failed: {reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
