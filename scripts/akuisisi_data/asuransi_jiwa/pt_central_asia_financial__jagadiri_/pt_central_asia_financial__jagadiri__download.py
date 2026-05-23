"""Download financial reports for PT Central Asia Financial (JAGADIRI)."""
import argparse
import logging
import sys
import re
from pathlib import Path
from calendar import month_name

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest,
    fetch_html_with_smart_fallback, current_timestamp
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_central_asia_financial__jagadiri_")
SOURCE_URL = "https://jagadiri.co.id/laporan-keuangan"
COMPANY_ID = "pt_central_asia_financial__jagadiri_"
COMPANY_NAME = "PT Central Asia Financial (JAGADIRI)"
CATEGORY = "asuransi_jiwa"

def fetch_jagadiri_pdfs(year, month, timeout=30):
    """Fetch JAGADIRI PDFs using Playwright (site requires JavaScript rendering)."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        try:
            page.goto(SOURCE_URL, wait_until="networkidle", timeout=timeout * 1000)
            content = page.content()

            # Extract all PDF URLs from page HTML
            pdf_urls = re.findall(r'https://[^\s"<>]+\.pdf', content)

            # Also try relative PDF links
            relative_pdfs = re.findall(r'href=["\'](/[^\s"\'<>]+\.pdf)', content)
            for rel_pdf in relative_pdfs:
                if rel_pdf.startswith('/'):
                    pdf_urls.append(f"https://jagadiri.co.id{rel_pdf}")

            # Filter by year and month with strict validation
            month_keywords = [month_name[month].lower(), str(month).zfill(2)]
            matching_pdfs = []

            for url in pdf_urls:
                url_lower = url.lower()
                # Check for year match
                if str(year) not in url_lower:
                    continue
                # Check for month match - must have explicit month indicator
                if any(kw in url_lower for kw in month_keywords):
                    matching_pdfs.append(url)

            LOGGER.info(f"Found {len(matching_pdfs)} PDFs for {year}-{month:02d}")

            # Return only matching PDFs, never fallback to all PDFs (would get wrong month)
            return content, SOURCE_URL, matching_pdfs
        finally:
            browser.close()

def download_pdf_via_playwright(pdf_url, output_path, timeout=30):
    """Download PDF using Playwright to bypass anti-bot detection."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        try:
            response = page.goto(pdf_url, timeout=timeout * 1000, wait_until="commit")
            page.wait_for_timeout(2000)

            if response.status == 200:
                pdf_bytes = page.pdf()
                with open(output_path, 'wb') as f:
                    f.write(pdf_bytes)
                LOGGER.info(f"Downloaded {len(pdf_bytes)} bytes via Playwright")
                return True
            else:
                LOGGER.error(f"HTTP {response.status} from {pdf_url}")
                return False
        except Exception as e:
            LOGGER.error(f"Playwright fetch failed: {e}")
            return False
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

    if not args.year or not args.month or not (1 <= args.month <= 12):
        LOGGER.error("Year and month (1-12) are required")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    LOGGER.info(f"Discovering PDF for {period}")

    try:
        # JAGADIRI requires Playwright for JavaScript rendering
        LOGGER.info("Using Playwright for JavaScript rendering")
        html, discovered_url, pdf_urls = fetch_jagadiri_pdfs(args.year, args.month, args.timeout)

        if pdf_urls:
            class Candidate:
                def __init__(self, url):
                    self.url = url
                    self.text = "PDF (extracted from page)"
            candidates = [Candidate(pdf_urls[0])]
        else:
            candidates = []

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

        pdf_url = candidates[0].url
        LOGGER.info(f"Found: {candidates[0].text[:60]}")

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

    # Try HTTP download first, fallback to Playwright
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
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        success = download_pdf_via_playwright(pdf_url, str(output_pdf), args.timeout)

        if success and output_pdf.exists():
            file_size = output_pdf.stat().st_size
            status = "downloaded"
            reason = f"Downloaded via Playwright ({file_size} bytes)"
        else:
            status = "error"
            reason = f"Failed to download via HTTP and Playwright"

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if status in ["downloaded", "skipped_existing"]:
        if status == "downloaded":
            LOGGER.info(f"Successfully downloaded to {output_pdf}")
        else:
            LOGGER.info(f"PDF already exists, keeping cached version")
        return 0
    else:
        LOGGER.error(f"Failed to download: {reason}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
