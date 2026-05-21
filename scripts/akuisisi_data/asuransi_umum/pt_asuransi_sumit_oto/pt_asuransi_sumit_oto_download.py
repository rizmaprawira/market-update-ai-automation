"""Download financial reports for PT Asuransi Sumit Oto.

The site lists reports at /profil/laporan-keuangan.
Each entry is a link to /admin/showdoc.php?j=lkf&vid=NNN which serves the PDF directly.
We use Playwright to find the correct vid for the target period, then download via requests.
"""
import argparse
import logging
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

from _downloader_base import (
    build_session, write_manifest, validate_pdf, current_timestamp,
    HEADERS, MONTH_LABELS
)

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_asuransi_sumit_oto")
SOURCE_URL = "https://aso.co.id/profil/laporan-keuangan"
BASE_URL = "https://aso.co.id"
COMPANY_ID = "pt_asuransi_sumit_oto"
COMPANY_NAME = "PT Asuransi Sumit Oto"
CATEGORY = "asuransi_umum"


def find_showdoc_url(year, month, timeout):
    """Use Playwright to find the showdoc URL for the target month/year."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")
    month_label = MONTH_LABELS[month]
    target_texts = [
        f"per 31 {month_label} {year}",
        f"per 30 {month_label} {year}",
        f"per 28 {month_label} {year}",
        f"per 29 {month_label} {year}",
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(2500)
            from bs4 import BeautifulSoup
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                if "showdoc" in href and any(t in text for t in [t.lower() for t in target_texts]):
                    return urljoin(BASE_URL, href)
            return None
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

    LOGGER.info(f"Finding showdoc URL for {period}")
    try:
        pdf_url = find_showdoc_url(args.year, args.month, args.timeout)
    except Exception as e:
        reason = f"browser error finding link: {e}"
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
        reason = "no showdoc link found for target period"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "no_pdf_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 0

    LOGGER.info(f"Found showdoc URL: {pdf_url}")

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {pdf_url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "already_exists", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with session.get(pdf_url, timeout=args.timeout, stream=True,
                         headers={"Referer": SOURCE_URL}) as response:
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
        "source_page_url": SOURCE_URL, "discovered_page_url": pdf_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": "success" if success else "failed",
        "reason": reason, "timestamp": current_timestamp()
    }])
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
