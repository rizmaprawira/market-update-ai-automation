"""Download financial reports for PT MNC Life Assurance."""
import argparse
import logging
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import write_manifest, write_debug_html, current_timestamp

LOGGER = logging.getLogger("download_pt_mnc_life_assurance")
SOURCE_URL = "https://www.mnclife.com/about/laporanKeuangan"
COMPANY_ID = "pt_mnc_life_assurance"
COMPANY_NAME = "PT MNC Life Assurance"
CATEGORY = "asuransi_jiwa"

MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def discover_mnc_life_pdf(year: int, month: int, timeout: int = 30):
    """Discover and download PDF by selecting dropdowns and clicking button."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto(SOURCE_URL, timeout=timeout * 1000, wait_until="networkidle")
            page.wait_for_timeout(2500)

            for _ in range(5):
                page.evaluate("window.scrollBy(0, 600)")
                page.wait_for_timeout(300)

            page.wait_for_timeout(1000)

            # Find "Laporan Keuangan Bulanan" section
            sections = page.query_selector_all(".section-file")
            bulanan_section = None

            for section in sections:
                h4 = section.query_selector("h4")
                if h4 and "Bulanan" in h4.inner_text():
                    bulanan_section = section
                    break

            if not bulanan_section:
                LOGGER.error("Could not find 'Laporan Keuangan Bulanan' section")
                return None

            LOGGER.info("Found 'Laporan Keuangan Bulanan' section")

            # Select year
            dropdowns = bulanan_section.query_selector_all(".dropdown-file")
            dropdowns[0].click()
            page.wait_for_timeout(700)

            year_str = str(year)
            all_elements = page.query_selector_all("p, span, div")
            for el in all_elements:
                try:
                    if el.inner_text().strip() == year_str:
                        el.click()
                        LOGGER.info(f"Selected year: {year}")
                        page.wait_for_timeout(1000)
                        break
                except:
                    pass

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

            # Select month
            bulanan_section.scroll_into_view_if_needed()
            page.wait_for_timeout(300)

            dropdowns = bulanan_section.query_selector_all(".dropdown-file")
            if len(dropdowns) < 2:
                LOGGER.error("Month dropdown not found")
                return None

            dropdowns[1].click(force=True)
            page.wait_for_timeout(700)

            month_name = MONTH_NAMES[month]
            all_elements = page.query_selector_all("p, span, div")
            for el in all_elements:
                try:
                    if el.inner_text().strip() == month_name:
                        el.click()
                        LOGGER.info(f"Selected month: {month_name}")
                        page.wait_for_timeout(1000)
                        break
                except:
                    pass

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

            # Click button and capture download
            button = bulanan_section.query_selector("button")
            if not button:
                LOGGER.error("Download button not found")
                return None

            LOGGER.info("Clicking download button...")
            with page.expect_download(timeout=timeout * 1000) as download_info:
                button.click()
                page.wait_for_timeout(2000)

            download = download_info.value
            LOGGER.info(f"PDF download captured: {download.suggested_filename}")
            return download

        except Exception as e:
            LOGGER.error(f"Error during discovery: {str(e)}")
            return None
        finally:
            context.close()
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

    if not args.year or not args.month or not 1 <= args.month <= 12:
        LOGGER.error("Year and month (1-12) are required")
        return 1

    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"

    LOGGER.info(f"Discovering PDF from {SOURCE_URL} (year={args.year}, month={args.month})")

    try:
        download = discover_mnc_life_pdf(args.year, args.month, timeout=args.timeout)

        if not download:
            reason = "failed to download PDF (dropdown selection or button click failed)"
            LOGGER.warning(reason)
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                "pdf_url": "", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "not_found", "reason": reason,
                "timestamp": current_timestamp()
            }])
            return 1

        LOGGER.info(f"PDF discovered via Playwright dropdown interaction")

        if args.discover_only:
            LOGGER.info("Discover-only mode: stopping after discovery")
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                "pdf_url": "(downloaded via Playwright)", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "discover_only", "reason": "discover-only mode",
                "timestamp": current_timestamp()
            }])
            return 0

        if args.dry_run:
            LOGGER.info("Dry-run: would download PDF")
            write_manifest(output_dir, [{
                "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
                "pdf_url": "(downloaded via Playwright)", "target_year": args.year, "target_month": args.month,
                "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
                "timestamp": current_timestamp()
            }])
            return 0

        output_dir.mkdir(parents=True, exist_ok=True)

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

        download.save_as(output_pdf)
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
        reason = f"error: {str(e)}"
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
