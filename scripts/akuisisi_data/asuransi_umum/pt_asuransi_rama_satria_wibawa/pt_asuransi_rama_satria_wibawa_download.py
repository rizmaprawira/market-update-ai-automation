"""Download financial reports for PT Asuransi Rama Satria Wibawa.

The site lists monthly reports as articles at /id/artikel/?category=laporan.
Each article contains a direct PDF link under /id/documents/.
"""
import argparse
import logging
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

from _downloader_base import (
    build_session, write_manifest, validate_pdf, current_timestamp,
    HEADERS, MONTH_NAMES
)

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
    from bs4 import BeautifulSoup
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_asuransi_rama_satria_wibawa")
SOURCE_URL = "https://ramains.com/id/artikel/?category=laporan"
BASE_URL = "https://ramains.com"
COMPANY_ID = "pt_asuransi_rama_satria_wibawa"
COMPANY_NAME = "PT Asuransi Rama Satria Wibawa"
CATEGORY = "asuransi_umum"


def find_pdf_url(year, month, timeout):
    """Browse listing page to find article for target period, then find PDF link."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")
    month_variants = MONTH_NAMES[month]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(2000)
            soup = BeautifulSoup(page.content(), "html.parser")
            article_url = None
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = (a.get_text(strip=True) + " " + href).lower()
                if str(year) in text and any(m in text for m in month_variants):
                    if "laporan" in text:
                        article_url = urljoin(BASE_URL, href)
                        break
            if not article_url:
                return None, None, SOURCE_URL
            LOGGER.info(f"Found article: {article_url}")
            page.goto(article_url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(1500)
            soup2 = BeautifulSoup(page.content(), "html.parser")
            for a in soup2.find_all("a"):
                href = a.get("href", "")
                if href and "/documents/" in href and href.endswith(".pdf"):
                    pdf_url = urljoin(BASE_URL, href)
                    return pdf_url, a.get_text(strip=True), article_url
            return None, None, article_url
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--debug-html", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / "raw_pdf" / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{period}.pdf"

    LOGGER.info(f"Finding article and PDF URL for {period}")
    try:
        pdf_url, pdf_text, discovered_url = find_pdf_url(args.year, args.month, args.timeout)
    except Exception as e:
        reason = f"browser error: {e}"
        LOGGER.error(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "failed", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    if not pdf_url:
        reason = "no PDF link found for target period"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "no_pdf_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 0

    LOGGER.info(f"Found PDF: {pdf_url}")

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
            "output_path": str(output_pdf), "status": "already_exists", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with session.get(pdf_url, timeout=args.timeout, stream=True,
                         headers={"Referer": discovered_url}) as response:
            status = response.status_code
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(output_dir), suffix=".part") as tmp:
                temp_path = Path(tmp.name)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
        data = temp_path.read_bytes()
        if not validate_pdf(data):
            temp_path.unlink()
            raise RuntimeError("Downloaded file is not a valid PDF")
        temp_path.replace(output_pdf)
        reason = f"HTTP {status}"
        success = True
        LOGGER.info(f"Successfully downloaded to {output_pdf} ({len(data)} bytes)")
    except Exception as e:
        reason = str(e)
        success = False
        LOGGER.error(f"Download failed: {reason}")

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": "success" if success else "failed",
        "reason": reason, "timestamp": current_timestamp()
    }])
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
