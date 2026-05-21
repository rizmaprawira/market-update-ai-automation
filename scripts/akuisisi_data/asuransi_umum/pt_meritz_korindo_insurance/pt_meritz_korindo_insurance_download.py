"""Download financial reports for PT Meritz Korindo Insurance.

Each month has its own WordPress page at:
  https://meritzkorindo.co.id/index.php/financial-statement-{year}-{month_name_id}/
That page embeds a Google Drive file via iframe. We extract the file ID and download it.
"""
import argparse
import logging
import re
import sys
import tempfile
from pathlib import Path

from _downloader_base import (
    build_session, write_manifest, validate_pdf, current_timestamp, HEADERS, MONTH_LABELS
)

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_meritz_korindo_insurance")
SOURCE_URL = "https://meritzkorindo.co.id/index.php/monthly-report/"
COMPANY_ID = "pt_meritz_korindo_insurance"
COMPANY_NAME = "PT Meritz Korindo Insurance"
CATEGORY = "asuransi_umum"

MONTH_SLUG = {
    1: "januari", 2: "februari", 3: "maret", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "agustus",
    9: "september", 10: "oktober", 11: "november", 12: "desember",
}


def get_drive_id(year, month, timeout):
    """Navigate to the individual month page and extract Google Drive file ID from iframe."""
    slug = MONTH_SLUG[month]
    page_url = f"https://meritzkorindo.co.id/index.php/financial-statement-{year}-{slug}/"
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 1200})
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(1500)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page.content(), "html.parser")
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src", "")
                m = re.search(r"drive\.google\.com/file/d/([^/]+)/", src)
                if m:
                    return m.group(1), page_url
            return None, page_url
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

    LOGGER.info(f"Finding Google Drive file ID for {period}")
    try:
        drive_id, page_url = get_drive_id(args.year, args.month, args.timeout)
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

    if not drive_id:
        reason = "no Google Drive iframe found on month page"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": page_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "no_pdf_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 0

    pdf_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    LOGGER.info(f"Found Google Drive file: {pdf_url}")

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {pdf_url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": page_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": page_url,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "already_exists", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with session.get(pdf_url, timeout=args.timeout, stream=True) as response:
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
        "source_page_url": SOURCE_URL, "discovered_page_url": page_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": "success" if success else "failed",
        "reason": reason, "timestamp": current_timestamp()
    }])
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
