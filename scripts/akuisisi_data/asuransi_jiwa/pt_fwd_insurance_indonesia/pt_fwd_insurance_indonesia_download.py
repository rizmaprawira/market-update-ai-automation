"""Download financial reports for PT FWD Insurance Indonesia."""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _downloader_base import (
    build_session, download_pdf, write_manifest, current_timestamp
)
from playwright.sync_api import sync_playwright

LOGGER = logging.getLogger("download_pt_fwd_insurance_indonesia")
ABOUT_PAGE_URL = "https://www.fwd.co.id/id/tentang-kami/"
COMPANY_ID = "pt_fwd_insurance_indonesia"
COMPANY_NAME = "PT FWD Insurance Indonesia"
CATEGORY = "asuransi_jiwa"

MONTH_LABELS = {
    1: "januari", 2: "februari", 3: "maret", 4: "april", 5: "mei", 6: "juni",
    7: "juli", 8: "agustus", 9: "september", 10: "oktober", 11: "november", 12: "desember"
}


def find_fwd_pdf_url(year: int, month: int, timeout: int = 30) -> str:
    """Navigate FWD's Tentang Kami page, find bulanan reports, select month, and get PDF URL."""
    month_name = MONTH_LABELS[month]
    month_display = f"{month_name.capitalize()} {year}"

    LOGGER.info(f"Looking for: {month_display}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(ABOUT_PAGE_URL, timeout=timeout*1000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Scroll to reports section
            page.evaluate("document.querySelector('[class*=\"CoverFlow\"]').scrollIntoView()")
            page.wait_for_timeout(1500)

            # Navigate carousel to bulanan (monthly) slide (index 2)
            LOGGER.debug("Navigating to bulanan slide...")
            navigate_result = page.evaluate('''() => {
                const track = document.querySelector('[class*="CoverFlow"] .slick-track');
                if (!track) return {success: false};

                const slides = track.querySelectorAll('[data-index]');
                if (slides.length === 0) return {success: false};

                const slideWidth = slides[0].offsetWidth;

                // Move to slide 2 (bulanan)
                track.style.transform = `translate3d(${-slideWidth * 2}px, 0px, 0px)`;

                // Update aria-hidden attributes
                slides.forEach(slide => {
                    const index = parseInt(slide.getAttribute('data-index'));
                    slide.setAttribute('aria-hidden', index !== 2 ? 'true' : 'false');
                    slide.classList.remove('slick-active', 'slick-center', 'slick-current');
                    if (index === 2) {
                        slide.classList.add('slick-active', 'slick-center', 'slick-current');
                    }
                });

                return {success: true};
            }''')

            if not navigate_result.get('success'):
                LOGGER.error("Failed to navigate carousel")
                page.close()
                browser.close()
                return None

            page.wait_for_timeout(500)

            # Click the dropdown in the bulanan section
            LOGGER.debug("Opening month dropdown...")
            page.evaluate('''() => {
                const slides = document.querySelectorAll('[class*="slick-slide"]');
                for (let slide of slides) {
                    const title = slide.querySelector('h4');
                    if (title && title.innerText.includes('bulanan')) {
                        const dropdown = slide.querySelector('[role="button"][aria-haspopup="listbox"]');
                        if (dropdown) {
                            dropdown.click();
                        }
                        break;
                    }
                }
            }''')

            page.wait_for_timeout(2000)

            # Select the target month from dropdown
            LOGGER.debug(f"Selecting {month_display}...")
            month_selected = page.evaluate(f'''() => {{
                const targetMonth = "{month_display}";
                const options = document.querySelectorAll('[role="option"]');

                // First try exact match
                for (let opt of options) {{
                    const text = opt.innerText.trim();
                    if (text === targetMonth) {{
                        opt.click();
                        opt.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                        return true;
                    }}
                }}

                // Fallback: try case-insensitive and flexible matching
                const monthLower = targetMonth.toLowerCase();
                for (let opt of options) {{
                    const text = opt.innerText.trim().toLowerCase();
                    if (text === monthLower || text.includes(monthLower)) {{
                        opt.click();
                        opt.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                        return true;
                    }}
                }}

                return false;
            }}''')

            if month_selected:
                LOGGER.debug(f"Successfully selected {month_display}")
            else:
                LOGGER.warning(f"Could not select {month_display}, will use available report")

            page.wait_for_timeout(2000)

            # Extract the PDF URL from the bulanan section
            pdf_url = page.evaluate('''() => {
                const slides = document.querySelectorAll('[class*="slick-slide"]');

                for (let slide of slides) {
                    const title = slide.querySelector('h4');
                    if (title && title.innerText.includes('bulanan')) {
                        const link = slide.querySelector('a[href*="/files"]');
                        if (link && link.href) {
                            return link.href;
                        }
                    }
                }
                return null;
            }''')

            page.close()
            browser.close()

            if pdf_url:
                LOGGER.info(f"Found PDF: {pdf_url[:80]}...")
                return pdf_url
            else:
                LOGGER.warning("Could not extract PDF URL")
                return None

    except Exception as e:
        LOGGER.error(f"Failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", type=int, help="Target year")
    parser.add_argument("--yyyy", dest="year", type=int, help="Target year (alias)")
    parser.add_argument("--month", type=int, help="Target month (1-12)")
    parser.add_argument("--mm", dest="month", type=int, help="Target month (alias)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Discovery only")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
    parser.add_argument("--force", action="store_true", help="Overwrite existing")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not args.year or not args.month:
        LOGGER.error("--year and --month are required")
        return 1

    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1

    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    # Search for PDF
    pdf_url = find_fwd_pdf_url(args.year, args.month, args.timeout)

    if not pdf_url:
        reason = "no PDF found"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": ABOUT_PAGE_URL, "discovered_page_url": ABOUT_PAGE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    LOGGER.info(f"Discovered: {pdf_url}")

    if args.discover_only:
        LOGGER.info("Discover-only mode")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": ABOUT_PAGE_URL, "discovered_page_url": ABOUT_PAGE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discover-only",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": ABOUT_PAGE_URL, "discovered_page_url": ABOUT_PAGE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run",
            "timestamp": current_timestamp()
        }])
        return 0

    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF exists: {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": ABOUT_PAGE_URL, "discovered_page_url": ABOUT_PAGE_URL,
            "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "exists",
            "timestamp": current_timestamp()
        }])
        return 0

    http_status, file_size = download_pdf(
        session, pdf_url, output_pdf, timeout=args.timeout, force=args.force
    )

    status = "downloaded" if http_status is not None else "skipped_existing"
    reason = f"HTTP {http_status} ({file_size} bytes)" if http_status else f"exists ({file_size} bytes)"

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": ABOUT_PAGE_URL, "discovered_page_url": ABOUT_PAGE_URL,
        "pdf_url": pdf_url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    if http_status is not None:
        LOGGER.info(f"Downloaded: {output_pdf}")
        return 0
    else:
        LOGGER.info(f"File exists: {output_pdf}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
