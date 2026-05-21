"""Download financial reports for PT Asuransi Etiqa Internasional Indonesia.

Note: Only use Indonesia page (etiqa.co.id/hubungan-investor/).
The international corporate site is NOT used.
Monthly reports are available as direct PDF links: /docs/LK/YYYY/Laporan Keuangan per DD MMM YYYY.pdf
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest,
    current_timestamp, MONTH_LABELS, PDFCandidate, fetch_html_browser_domready
)

LOGGER = logging.getLogger("download_pt_asuransi_etiqa_internasional_indonesia")
SOURCE_URL = "https://www.etiqa.co.id/hubungan-investor/"
COMPANY_ID = "pt_asuransi_etiqa_internasional_indonesia"
COMPANY_NAME = "PT Asuransi Etiqa Internasional Indonesia"
CATEGORY = "asuransi_umum"

def discover_etiqa_reports(html, base_url, year, month):
    """Extract Etiqa monthly PDF links from Indonesia page HTML.

    Files are formatted as: Laporan Keuangan per 31 Jan 2026.pdf, etc.
    Uses month label matching to prefer exact month over date parsing.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    candidates = []
    soup = BeautifulSoup(html, 'html.parser')
    month_label = MONTH_LABELS[month]

    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        if not href or not href.lower().endswith('.pdf'):
            continue

        text = link.get_text(strip=True)
        blob = f"{text} {href}".lower()

        if str(year) in blob:
            url = urljoin(base_url, href)
            score = 50
            month_label_lower = month_label.lower()
            if month_label_lower in blob:
                score += 50
            if 'laporan' in blob and 'keuangan' in blob:
                score += 20
            candidates.append(PDFCandidate(url=url, text=text, score=score, discovered_url=base_url))

    return sorted(candidates, key=lambda x: x.score, reverse=True)[:1]

def main():
    parser = argparse.ArgumentParser(description=f"Download {COMPANY_NAME} financial reports")
    parser.add_argument("--year", "--yyyy", dest="year", type=int, required=True, help="Target year")
    parser.add_argument("--month", "--mm", dest="month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    parser.add_argument("--dry-run", action="store_true", help="Download validation without writing file")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF")
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

    month_label = MONTH_LABELS[args.month]
    LOGGER.info(f"Fetching from Indonesia page: {SOURCE_URL}")

    try:
        html, discovered_url = fetch_html_browser_domready(SOURCE_URL, args.timeout, extra_wait_ms=1500)
    except Exception as e:
        reason = f"failed to fetch: {e}"
        LOGGER.error(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": SOURCE_URL,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "error", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 1

    candidates = discover_etiqa_reports(html, SOURCE_URL, args.year, args.month)

    if not candidates:
        reason = f"no PDF candidates found for {month_label} {args.year}"
        LOGGER.warning(reason)
        write_manifest(output_dir, [{
            "category": CATEGORY, "company_id": COMPANY_ID, "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL, "discovered_page_url": discovered_url,
            "pdf_url": "", "target_year": args.year, "target_month": args.month,
            "output_path": str(output_pdf), "status": "not_found", "reason": reason,
            "timestamp": current_timestamp()
        }])
        return 0

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

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        http_status, file_size = download_pdf(
            session, selected_candidate.url, output_pdf, timeout=args.timeout, force=args.force
        )
        success = True
        reason = (
            f"downloaded monthly report ({http_status}, bytes={file_size})"
            if http_status is not None
            else f"existing valid PDF kept (bytes={file_size})"
        )
        status = "downloaded" if http_status is not None else "skipped_existing"
    except Exception as e:
        success = False
        reason = f"failed to download: {e}"
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
