"""Download financial reports for PT Pan Pacific Insurance.

Reports are listed in a table at /about-us/financial-highlights/.
Each row has the report name and a SharePoint "Download" link.
We find the row for the target month/year and download from the SharePoint URL.
"""
import argparse
import logging
import sys
import tempfile
from pathlib import Path

from _downloader_base import (
    build_session, write_manifest, validate_pdf, current_timestamp,
    HEADERS, MONTH_LABELS
)

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
    from bs4 import BeautifulSoup
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_pan_pacific_insurance")
SOURCE_URL = "https://www.panfic.com/about-us/financial-highlights/"
COMPANY_ID = "pt_pan_pacific_insurance"
COMPANY_NAME = "PT Pan Pacific Insurance"
CATEGORY = "asuransi_umum"


def find_sharepoint_url(year, month, timeout):
    """Find the SharePoint link for the target period by scanning the table."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")
    month_label = MONTH_LABELS[month].upper()
    target_text = f"LAPORAN KEUANGAN {month_label} {year}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(3000)
            soup = BeautifulSoup(page.content(), "html.parser")
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    cell_text = " ".join(c.get_text(strip=True) for c in cells).upper()
                    if month_label in cell_text and str(year) in cell_text and "LAPORAN KEUANGAN" in cell_text:
                        for a in row.find_all("a"):
                            href = a.get("href", "")
                            if href and "sharepoint.com" in href:
                                return href.rstrip(), SOURCE_URL
            return None, SOURCE_URL
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

    LOGGER.info(f"Finding SharePoint download URL for {period}")
    try:
        sharepoint_url, discovered_url = find_sharepoint_url(args.year, args.month, args.timeout)
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

    if not sharepoint_url:
        reason = "no SharePoint link found for target period"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "no_pdf_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 0

    # Append &download=1 to get direct PDF download from SharePoint
    sep = "&" if "?" in sharepoint_url else "?"
    pdf_url = sharepoint_url + sep + "download=1"
    LOGGER.info(f"Found SharePoint URL, download link: {pdf_url[:80]}...")

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
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": "success" if success else "failed",
        "reason": reason, "timestamp": current_timestamp()
    }])
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
