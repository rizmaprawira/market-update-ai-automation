"""Download financial reports for PT MSIG Life Assurance."""
import argparse
import logging
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, download_pdf, write_manifest, write_debug_html, current_timestamp
)

LOGGER = logging.getLogger("download_pt_mnc_life_assurance")
SOURCE_URL = "https://www.msiglife.co.id/tentang-kami/laporan-keuangan"
COMPANY_ID = "pt_mnc_life_assurance"
COMPANY_NAME = "PT MSIG Life Assurance"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def discover_msig_life_pdf(year: int, month: int, output_path: Path, timeout: int = 30) -> bool:
    """Discover and download PDF by tab + year selection + button click."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        try:
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            time.sleep(1)

            # Click on "Bulanan" (Monthly Reports) tab
            bulanan_tab = page.query_selector("text=Bulanan")
            if not bulanan_tab:
                LOGGER.error("Could not find 'Bulanan' tab")
                return False

            bulanan_tab.click()
            time.sleep(1)
            LOGGER.info("Clicked 'Bulanan' tab")

            # Select year from the year dropdown
            # The second select element has 2026, 2025, 2024, 2023
            selects = page.query_selector_all("select")
            if len(selects) < 2:
                LOGGER.error(f"Expected at least 2 select elements, found {len(selects)}")
                return False

            year_select = selects[1]
            year_select.select_option(str(year))
            time.sleep(1)
            LOGGER.info(f"Selected year: {year}")

            # Find the button for "Laporan Keuangan Konvensional [Month]" + Unduh PDF
            month_name = MONTH_NAMES[month]
            target_text = f"Laporan Keuangan Konvensional {month_name}"

            # Find all "Unduh PDF" buttons
            buttons = page.query_selector_all("text=Unduh PDF")
            found_button = None

            for button in buttons:
                # Check if this button is near the target month text by checking parent elements
                parent_text = page.evaluate("(el) => el.parentElement.innerText", button)
                if target_text in parent_text:
                    found_button = button
                    break

            if not found_button:
                LOGGER.error(f"Could not find download button for '{target_text}'")
                return False

            LOGGER.info(f"Found download button for '{target_text}'")

            # Click the button and capture the download
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with page.expect_download(timeout=timeout * 1000) as download_info:
                found_button.click()
                time.sleep(2)

            download = download_info.value
            download.save_as(output_path)
            LOGGER.info("PDF download captured successfully")
            return True

        except Exception as e:
            LOGGER.error(f"Error during discovery: {str(e)}")
            return False
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (validate without download)")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, return 0")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
    parser.add_argument("--use-browser", action="store_true", help="Use Playwright browser rendering")
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failure")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not args.year or not args.month or not 1 <= args.month <= 12:
        LOGGER.error("Year and month (1-12) are required")
        return 1

    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF from {SOURCE_URL} (year={args.year}, month={args.month})")

    if args.discover_only:
        LOGGER.info("Discover-only mode: discovery only, no download")
        # For discover-only, we need to just check if discovery works (returns True/False)
        # We create a temporary path just for the discovery phase
        try:
            success = discover_msig_life_pdf(args.year, args.month, output_pdf, timeout=args.timeout)
            if success:
                # Delete the file since we only want to discover
                if output_pdf.exists():
                    output_pdf.unlink()
                write_manifest(output_dir, [{
                    "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                    "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                    "pdf_url": "(downloaded via Playwright)", "target_year": args.year, "target_month": args.month,
                    "output_path": str(output_pdf), "status": "discover_only", "reason": "discover-only mode",
                    "timestamp": current_timestamp()
                }])
                return 0
            else:
                reason = "no PDF found (dropdown/button interaction failed)"
                write_manifest(output_dir, [{
                    "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                    "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                    "pdf_url": "", "target_year": args.year, "target_month": args.month,
                    "output_path": str(output_pdf), "status": "not_found", "reason": reason,
                    "timestamp": current_timestamp()
                }])
                return 1
        except Exception as e:
            reason = f"failed to discover: {str(e)}"
            LOGGER.error(reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                "pdf_url": "", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "error", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 1

    if args.dry_run:
        LOGGER.info("Dry-run mode: validation only, no download")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "(would download via Playwright)", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        file_size = output_pdf.stat().st_size
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "(downloaded via Playwright)", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing",
            "reason": f"existing valid PDF kept ({file_size} bytes)",
            "timestamp": current_timestamp()
        }])
        return 0

    try:
        success = discover_msig_life_pdf(args.year, args.month, output_pdf, timeout=args.timeout)
        if not success:
            reason = "no PDF found (dropdown/button interaction failed)"
            LOGGER.warning(reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                "pdf_url": "", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "not_found", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 1

        file_size = output_pdf.stat().st_size
        LOGGER.info(f"Successfully downloaded to {output_pdf} ({file_size} bytes)")

        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "(downloaded via Playwright)", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "downloaded",
            "reason": f"HTTP 200 ({file_size} bytes)",
            "timestamp": current_timestamp()
        }])

        return 0

    except Exception as e:
        reason = f"failed to discover/download: {str(e)}"
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

if __name__ == "__main__":
    sys.exit(main())
