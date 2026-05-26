"""Download financial reports for PT Avrist Assurance."""
import argparse
import logging
import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import write_manifest, current_timestamp

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOGGER = logging.getLogger("download_pt_avrist_assurance")
SOURCE_URL = "https://www.avrist.com/tentang-avrist-life/tentang-avrist-life?tab=Laporan+Perusahaan"
COMPANY_ID = "pt_avrist_assurance"
COMPANY_NAME = "PT Avrist Assurance"
CATEGORY = "asuransi_jiwa"

def download_avrist_report(url, year, month, output_path, timeout=60):
    """Download Avrist konvensional report by setting dropdowns and clicking Unduh button."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed")

    indonesian_months = {
        1: 'januari', 2: 'februari', 3: 'maret', 4: 'april', 5: 'mei', 6: 'juni',
        7: 'juli', 8: 'agustus', 9: 'september', 10: 'oktober', 11: 'november', 12: 'desember'
    }
    target_month = indonesian_months.get(month, '').lower()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Load the page
            LOGGER.info(f"Loading {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000 * 0.6))
            page.wait_for_timeout(3000)

            # Click on "Laporan Keuangan" sidebar item
            LOGGER.info("Clicking Laporan Keuangan sidebar...")
            sidebar_items = page.query_selector_all('div.cursor-pointer')
            for item in sidebar_items:
                if item.text_content().strip() == 'Laporan Keuangan':
                    item.click()
                    page.wait_for_timeout(4000)
                    break

            # Set year and month dropdowns
            LOGGER.info(f"Setting year={year}, month={month}")
            page.evaluate(f"""
            () => {{
                const selects = document.querySelectorAll('select');
                if (selects[0]) selects[0].value = '{year}';
                if (selects[1]) selects[1].value = '{month:02d}';
            }}
            """)
            page.wait_for_timeout(3000)

            # Find and click the Unduh button for konvensional report
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # Check if the konvensional report is present
            found = False
            for elem in soup.find_all(['p', 'div']):
                text = elem.get_text(strip=True).lower()
                if str(year) in text and target_month in text and 'konvensional' in text:
                    LOGGER.info(f"Found report: {text[:60]}")
                    found = True
                    break

            if not found:
                LOGGER.error(f"Report not found for {year}-{month:02d}")
                return False

            # Find all Unduh buttons and use the first one
            all_buttons = page.query_selector_all('button')
            for btn in all_buttons:
                if btn.text_content().lower().strip() == 'unduh':
                    LOGGER.info("Clicking Unduh button...")
                    with page.expect_download() as download_info:
                        btn.click()

                    download = download_info.value
                    download.save_as(output_path)

                    file_size = Path(output_path).stat().st_size
                    LOGGER.info(f"Downloaded {file_size} bytes to {output_path}")
                    return True

            LOGGER.error("No Unduh button found")
            return False

        except Exception as e:
            LOGGER.error(f"Download failed: {e}")
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
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failure")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not args.year or not 1 <= args.month <= 12:
        LOGGER.error("Year and month (1-12) are required")
        return 1

    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.discover_only or args.dry_run:
        LOGGER.info("Discover/dry-run mode: skipping download")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run" if args.dry_run else "discover_only",
            "reason": "dry-run mode" if args.dry_run else "discover-only mode",
            "timestamp": current_timestamp()
        }])
        return 0

    # Create output directory
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Download the report
    success = download_avrist_report(SOURCE_URL, args.year, args.month, str(output_pdf), args.timeout)

    if success:
        file_size = output_pdf.stat().st_size
        status = "downloaded"
        reason = f"Downloaded ({file_size} bytes)"
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
        returncode = 0
    else:
        status = "error"
        reason = "Failed to download"
        returncode = 1

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
        "pdf_url": "", "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    return returncode


if __name__ == "__main__":
    sys.exit(main())
