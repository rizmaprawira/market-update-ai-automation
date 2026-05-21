"""Download financial reports for PT Asuransi Bangun Askrida."""
import argparse
import logging
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _downloader_base import (
    build_session, extract_pdf_links, download_pdf, write_manifest, write_debug_html,
    fetch_html_static, fetch_html_browser, fetch_html_with_smart_fallback,
    discover_download_candidate, current_timestamp, sync_playwright, PDFCandidate, score_candidate
)

LOGGER = logging.getLogger("download_pt_asuransi_bangun_askrida")
SOURCE_URL = "https://askrida.com/laporan"
COMPANY_ID = "pt_asuransi_bangun_askrida"
COMPANY_NAME = "PT Asuransi Bangun Askrida"
CATEGORY = "asuransi_umum"


def _to_drive_download_url(url):
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url or "")
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return url


def _extract_candidates_from_askrida_table(html, page_url, year, month):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#table-report tbody tr")
    candidates = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        title = " ".join(cols[0].stripped_strings)
        category = " ".join(cols[1].stripped_strings)
        date_text = " ".join(cols[2].stripped_strings)
        context = f"{title} {category} {date_text}"
        score = score_candidate(context, year, month)
        for link in row.select("a[href]"):
            href = link.get("href", "").strip()
            if not href:
                continue
            low = href.lower()
            if "drive.google.com" in low:
                href = _to_drive_download_url(href)
            elif ".pdf" not in low:
                continue
            candidates.append(
                PDFCandidate(
                    url=href,
                    text=context,
                    score=score,
                    discovered_url=page_url,
                )
            )
    return candidates


def discover_askrida_paginated_candidates(year, month, timeout):
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed")

    candidates = []
    seen_urls = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2200})
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(1200)

            def collect_current_page():
                html_now = page.content()
                for cand in extract_pdf_links(html_now, page.url, year, month):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)
                for cand in _extract_candidates_from_askrida_table(html_now, page.url, year, month):
                    if cand.url not in seen_urls:
                        seen_urls.add(cand.url)
                        candidates.append(cand)

            collect_current_page()
            page_links = page.locator("#table-report_paginate a.page-link")
            texts = page_links.all_inner_texts()
            numeric_pages = sorted({int(t.strip()) for t in texts if t.strip().isdigit()})

            for page_num in numeric_pages:
                if page_num <= 1:
                    continue
                link = page.locator(
                    "#table-report_paginate a.page-link", has_text=str(page_num)
                ).first
                if link.count() == 0:
                    continue
                link.click()
                page.wait_for_timeout(700)
                collect_current_page()
        finally:
            browser.close()

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
    
    candidates = extract_pdf_links(html, discovered_url, args.year, args.month)
    if not candidates:
        try:
            paginated = discover_askrida_paginated_candidates(args.year, args.month, args.timeout)
            if paginated:
                matched = [c for c in paginated if c.score >= 50]
                if matched:
                    candidates = matched
                    LOGGER.info(f"Found {len(candidates)} period-matching candidates from paginated Askrida table")
                else:
                    LOGGER.info(
                        "Paginated Askrida table found %d links but none matched target period %04d-%02d",
                        len(paginated), args.year, args.month
                    )
        except Exception as e:
            LOGGER.warning(f"Askrida paginated discovery failed: {e}")

    if not candidates:
        try:
            fallback = discover_download_candidate(
                session, html, discovered_url, args.year, args.month, timeout=args.timeout
            )
            candidates = [fallback]
            LOGGER.info(f"Discovered candidate via multi-hop fallback: {fallback.url}")
        except Exception:
            pass
    candidates = [c for c in candidates if c.score >= 50]

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
