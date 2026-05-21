"""Download financial reports for PT BRI Asuransi Indonesia."""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback, current_timestamp,
    discover_download_candidate
)

LOGGER = logging.getLogger("download_pt_bri_asuransi_indonesia")
SOURCE_URL = "https://brins.co.id/home/economicvalue"
COMPANY_ID = "pt_bri_asuransi_indonesia"
COMPANY_NAME = "PT BRI Asuransi Indonesia"
CATEGORY = "asuransi_umum"

def discover_bri_reports(html, base_url, year, month, timeout=30):
    """
    BRI serves reports via broadcast.api.brinesia.app with dynamic gallery IDs per month.
    Gallery IDs are loaded dynamically by the Angular app.
    Known working gallery IDs:
      - March 2026: F5D59F0029C3F1CC1429EF6FF98B5C371EA3855142E47661C52EA26858BA46A9
      - April 2026: 3E95B044B4BFC897EEFD9586C83FC409CAB6E3DD6101B90DFEAEFBDD8835861F
    """
    import re
    from _downloader_base import build_session as _build_session, PDFCandidate

    candidates = []

    # Known gallery IDs for 2026 (these should be updated as new months are published)
    gallery_ids_2026 = {
        1: "",  # January - check when available
        2: "",  # February
        3: "F5D59F0029C3F1CC1429EF6FF98B5C371EA3855142E47661C52EA26858BA46A9",  # March
        4: "3E95B044B4BFC897EEFD9586C83FC409CAB6E3DD6101B90DFEAEFBDD8835861F",  # April
        5: "",  # May
    }

    if year == 2026 and month in gallery_ids_2026:
        gallery_id = gallery_ids_2026[month]
        if not gallery_id:
            LOGGER.debug(f"Gallery ID for {year}-{month:02d} not yet known")
            return []
    else:
        # Try to extract gallery ID from HTML (if rendered with data)
        gallery_matches = re.findall(r'[A-F0-9]{64}', html)
        if not gallery_matches:
            LOGGER.debug(f"Could not find gallery ID for {year}-{month:02d}")
            return []
        gallery_id = gallery_matches[0]

    # Build URL with Indonesian month name
    month_names = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    month_name = month_names.get(month, "")

    if not month_name:
        return []

    pdf_url = f"https://broadcast.api.brinesia.app/FinancialReportGallery/{gallery_id}/LaporanKeuanganPublikasi{month_name}{year}Konvensional.pdf"

    # Verify URL exists
    try:
        session = _build_session()
        r = session.head(pdf_url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            candidates.append(PDFCandidate(
                url=pdf_url,
                text=f"BRI Report {month_name} {year}",
                score=100,
                discovered_url=base_url
            ))
        else:
            LOGGER.debug(f"BRI URL returned {r.status_code}")
    except Exception as e:
        LOGGER.debug(f"BRI URL verification failed: {e}")

    return candidates

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, no download")
    parser.add_argument("--dry-run", action="store_true", help="Validate download without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
    parser.add_argument("--use-browser", action="store_true", help="Use Playwright browser rendering")
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failure")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    
    if not 1 <= args.month <= 12:
        LOGGER.error("Month must be 1-12")
        return 1
    
    session = build_session()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / CATEGORY / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / "_debug_html"
    
    LOGGER.info(f"Fetching from {SOURCE_URL}")
    
    try:
        if args.use_browser:
            LOGGER.info("Using Playwright browser rendering")
            html, discovered_url = fetch_html_browser(SOURCE_URL, args.timeout)
        else:
            html, discovered_url, used_browser = fetch_html_with_smart_fallback(
                session, SOURCE_URL, args.year, args.month, args.timeout
            )
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
    
    # Try BRI-specific discovery first (API-based approach)
    candidates = discover_bri_reports(html, discovered_url, args.year, args.month, args.timeout)

    # Fallback: generic extraction
    if not candidates:
        candidates = extract_pdf_links(html, discovered_url, args.year, args.month)

    # Fallback: deeper discovery if generic extraction fails
    if not candidates:
        try:
            LOGGER.info("Generic extraction failed, trying deeper discovery")
            candidate = discover_download_candidate(session, html, discovered_url, args.year, args.month, args.timeout)
            candidates = [candidate]
        except Exception as e:
            LOGGER.debug(f"Deeper discovery failed: {e}")

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
    
    selected_candidate = candidates[0]
    LOGGER.info(f"Selected: {selected_candidate.text[:60]}")
    

    if args.discover_only:
        LOGGER.info(f"Discovery complete: {selected_candidate.url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": "discovery complete",
            "timestamp": current_timestamp()
        }])
        return 0

    if args.dry_run:
        LOGGER.info(f"Dry-run: would download from {selected_candidate.url}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "dry_run", "reason": "dry-run mode",
            "timestamp": current_timestamp()
        }])
        return 0
    
    if output_pdf.exists() and not args.force:
        LOGGER.info(f"PDF already exists at {output_pdf}")
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "skipped_existing", "reason": "file exists",
            "timestamp": current_timestamp()
        }])
        return 0
    
    try:
        http_status, file_size = download_pdf(
            session, selected_candidate.url, output_pdf, timeout=args.timeout, force=args.force
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
        reason = (
            f"HTTP {http_status} ({file_size} bytes)"
            if http_status is not None
            else f"existing valid ({file_size} bytes)"
        )
        LOGGER.info(f"PDF {'downloaded' if http_status else 'skipped (existing)'}: {output_pdf}")
        exit_code = 0
    except Exception as e:
        status = "error"
        reason = str(e)
        LOGGER.error(f"Download failed: {reason}")
        exit_code = 1

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status, "reason": reason,
        "timestamp": current_timestamp()
    }])

    return exit_code

if __name__ == "__main__":
    sys.exit(main())
