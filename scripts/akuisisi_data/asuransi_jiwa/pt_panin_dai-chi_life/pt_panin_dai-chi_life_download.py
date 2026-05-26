"""Download financial reports for PT Panin Dai-Chi Life Insurance."""
import argparse
import logging
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_browser_domready, fetch_html_with_smart_fallback, current_timestamp,
    normalize_text, matches_target_period, score_candidate, MONTH_LABELS, PDFCandidate
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_panin_dai-chi_life")
SOURCE_URL = "http://www.panindai-ichilife.co.id/id/laporan-keuangan"
COMPANY_ID = "pt_panin_dai-chi_life"
COMPANY_NAME = "PT Panin Dai-Chi Life"
CATEGORY = "asuransi_jiwa"

def fetch_html_with_stealth(url, timeout=30):
    """Fetch HTML using headless browser with no-sandbox."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            page.wait_for_timeout(2000)
            html = page.content()
            final_url = page.url
            browser.close()
            return html, final_url
        except Exception as e:
            browser.close()
            raise RuntimeError(f"browser fetch failed: {e}") from e

def extract_pdf_links(html, base_url, year, month):
    import re
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []

    for link in soup.find_all('a'):
        href = link.get('href', '').strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue

        text = link.get_text(strip=True)
        if "download" not in text.lower():
            continue

        parent_text = ""
        ancestor_text = ""
        if link.parent:
            parent_text = link.parent.get_text(" ", strip=True)
            # Also check grandparent and great-grandparent for card container
            if link.parent.parent:
                ancestor_text = link.parent.parent.get_text(" ", strip=True)

        blob_text = " ".join(part for part in [text, parent_text, ancestor_text, href] if part)
        blob = normalize_text(blob_text)
        url = urljoin(base_url, href)

        if not (str(year) in blob and MONTH_LABELS[month].lower() in blob):
            continue

        score = score_candidate(blob_text, year, month)
        score += 50
        # Boost score if the immediate parent/card contains ONLY the target month
        # (not multiple months in the same card)
        if parent_text and MONTH_LABELS[month].lower() in normalize_text(parent_text):
            score += 100
        candidates.append(PDFCandidate(url=url, text=text, score=score, discovered_url=base_url))

    return sorted(candidates, key=lambda x: x.score, reverse=True)

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

    if not args.year or not args.month:
        LOGGER.error("Year and month are required (use --year/--yyyy and --month/--mm)")
        return 1

    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Fetching from {SOURCE_URL}")

    try:
        try:
            html, discovered_url = session.get(SOURCE_URL, timeout=args.timeout).text, SOURCE_URL
            LOGGER.info(f"Static fetch succeeded ({len(html)} bytes)")
        except Exception as e:
            LOGGER.info(f"Static fetch failed ({e}), falling back to browser")
            html, discovered_url = fetch_html_with_stealth(SOURCE_URL, args.timeout)
            LOGGER.info(f"Browser fetch got {len(html)} bytes")
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
    LOGGER.info(f"Extraction found {len(candidates)} candidates")

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

    pdf_url = candidates[0].url
    LOGGER.info(f"Discovered PDF URL: {pdf_url}")

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
        file_size = output_pdf.stat().st_size
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": f"existing valid PDF kept ({file_size} bytes)",
            "timestamp": current_timestamp()
        }])
        return 0

    http_status, file_size = download_pdf(
        session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
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
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if status == "downloaded":
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
    else:
        LOGGER.info(f"Using existing PDF: {output_pdf}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
