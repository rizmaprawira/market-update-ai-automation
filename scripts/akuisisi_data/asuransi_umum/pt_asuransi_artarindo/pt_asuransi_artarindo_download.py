"""Download financial reports for PT Asuransi Artarindo."""
import argparse
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback,
    discover_download_candidate, current_timestamp, PDFCandidate
)

LOGGER = logging.getLogger("download_pt_asuransi_artarindo")
SOURCE_URL = "https://artarindo.co.id/aboutus"
COMPANY_ID = "pt_asuransi_artarindo"
COMPANY_NAME = "PT Asuransi Artarindo"
CATEGORY = "asuransi_umum"
REPORT_API_URL = "https://svc01.artarindo.id/public/website/api/report"


def _to_drive_download_url(url):
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url or "")
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return url


def discover_artarindo_api_candidates(session, year, month):
    response = session.get(REPORT_API_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return []

    candidates = []
    for item in items:
        try:
            item_year = int(item.get("year", 0))
            item_month = int(item.get("month", 0))
        except Exception:
            continue
        if item_year <= 0 or item_month <= 0 or item_month > 12:
            continue
        report_url = str(item.get("reportURL") or "").strip()
        if not report_url:
            continue
        category_id = item.get("categoryID", item.get("categoryId"))
        if str(category_id) != "1":
            continue
        label = f"Laporan Keuangan Bulan {item_month:02d}-{item_year}"
        score = 0
        if item_year == year and item_month == month:
            score += 1000
        elif item_year == year:
            score += 300 - abs(item_month - month)
        else:
            score += 50
        candidates.append(
            PDFCandidate(
                url=_to_drive_download_url(report_url),
                text=label,
                score=score,
                discovered_url=REPORT_API_URL,
            )
        )
    return sorted(candidates, key=lambda c: c.score, reverse=True)

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no download")
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
    
    candidates = []
    try:
        candidates = discover_artarindo_api_candidates(session, args.year, args.month)
        if candidates:
            discovered_url = REPORT_API_URL
            LOGGER.info(f"Found {len(candidates)} candidates from Artarindo report API")
    except Exception as e:
        LOGGER.warning(f"Artarindo API discovery failed, falling back to HTML: {e}")

    if not candidates:
        candidates = extract_pdf_links(html, discovered_url, args.year, args.month)
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
