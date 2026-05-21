"""Download financial reports for PT Asuransi Digital Bersama Tbk.."""
import argparse
import logging
import sys
import time
from pathlib import Path
from collections import namedtuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback,
    discover_download_candidate, current_timestamp, MONTH_LABELS
)

Candidate = namedtuple("Candidate", ["url", "text"])

LOGGER = logging.getLogger("download_pt_asuransi_digital_bersama_tbk")
SOURCE_URL = "https://adbinsure.com/kinerja-keuangan"
STORAGE_BASE = "https://adbinsure.com/storage/files/"
COMPANY_ID = "pt_asuransi_digital_bersama_tbk"
COMPANY_NAME = "PT Asuransi Digital Bersama Tbk."
CATEGORY = "asuransi_umum"


def discover_storage_candidates(session, year, month, timeout=30):
    """Try to find PDF in ADB Insure storage folder with various naming patterns."""
    candidates = []

    # Pattern 1: laporan_keuangan_pt_asuransi_digital_bersama_publikasi_web_[MONTHABBR]_[YY].pdf
    # e.g., laporan_keuangan_pt_asuransi_digital_bersama_publikasi_web_mar_26.pdf
    month_abbr = MONTH_LABELS[month].lower()[:3]
    yy = str(year)[2:]

    pattern1 = f"laporan_keuangan_pt_asuransi_digital_bersama_publikasi_web_{month_abbr}_{yy}.pdf"
    url1 = STORAGE_BASE + pattern1
    try:
        r = session.head(url1, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            candidates.append(Candidate(url=url1, text=f"Storage pattern 1: {pattern1}"))
            LOGGER.info(f"✓ Found via pattern 1: {pattern1}")
    except Exception as e:
        LOGGER.debug(f"Pattern 1 failed: {e}")

    # Pattern 2: LAPKEU_BULANAN_[MONTHABBR]_[YY].pdf
    # e.g., LAPKEU_BULANAN_MAR_26.pdf
    month_abbr_upper = MONTH_LABELS[month].upper()[:3]
    pattern2 = f"LAPKEU_BULANAN_{month_abbr_upper}_{yy}.pdf"
    url2 = STORAGE_BASE + pattern2
    try:
        r = session.head(url2, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            candidates.append(Candidate(url=url2, text=f"Storage pattern 2: {pattern2}"))
            LOGGER.info(f"✓ Found via pattern 2: {pattern2}")
    except Exception as e:
        LOGGER.debug(f"Pattern 2 failed: {e}")

    # Pattern 3: lapkeu [MM][YY].pdf (with space or %20)
    # e.g., lapkeu 0326.pdf or lapkeu%200326.pdf
    mm = f"{month:02d}"
    pattern3 = f"lapkeu%20{mm}{yy}.pdf"
    url3 = STORAGE_BASE + pattern3
    try:
        r = session.head(url3, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            candidates.append(Candidate(url=url3, text=f"Storage pattern 3: {pattern3}"))
            LOGGER.info(f"✓ Found via pattern 3: {pattern3}")
    except Exception as e:
        LOGGER.debug(f"Pattern 3 failed: {e}")

    return candidates

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Download validation without writing file")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
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
    
    candidates = extract_pdf_links(html, discovered_url, args.year, args.month)

    # Try ADB Insure storage folder with pattern matching
    if not candidates:
        LOGGER.info("Trying ADB Insure storage folder patterns...")
        storage_candidates = discover_storage_candidates(session, args.year, args.month, args.timeout)
        if storage_candidates:
            candidates = storage_candidates
            LOGGER.info(f"Found {len(candidates)} candidate(s) in storage folder")

    # Try generic multi-hop fallback
    if not candidates:
        try:
            fallback = discover_download_candidate(
                session, html, discovered_url, args.year, args.month, timeout=args.timeout
            )
            candidates = [fallback]
            LOGGER.info(f"Discovered candidate via multi-hop fallback: {fallback.url}")
        except Exception:
            pass

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
        reason = "discovery completed; download skipped by --discover-only"
        LOGGER.info(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "discover_only", "reason": reason,
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
        success = True
        reason = (
            f"downloaded conventional financial report PDF (http_status={http_status}, bytes={file_size})"
            if http_status is not None
            else f"existing valid PDF was kept (bytes={file_size})"
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
    except Exception as e:
        success = False
        reason = f"failed to download PDF: {e}"
        status = "error"

    write_manifest(output_dir, [{
        "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
        "pdf_url": selected_candidate.url, "target_year": args.year, "target_month": args.month,
        "output_path": str(output_pdf), "status": status,
        "reason": reason, "timestamp": current_timestamp()
    }])
    
    if success:
        LOGGER.info(f"Successfully downloaded to {output_pdf}")
    else:
        LOGGER.error(f"Failed to download: {reason}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
