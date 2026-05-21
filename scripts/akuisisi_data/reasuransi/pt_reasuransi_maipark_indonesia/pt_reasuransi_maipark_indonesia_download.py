from __future__ import annotations

"""Download MAIPARK's conventional financial report PDF.

This script is specific to PT Reasuransi MAIPARK Indonesia and downloads financial
reports from their corporate reporting page. Supports pagination across multiple pages.

Usage:
    python scripts/download/reasuransi/download_maipark.py \
        --year 2026 --month 3 \
        --output-root data \
        [--discover-only] \
        [--use-browser] \
        [--debug-html] \
        [--dry-run] \
        [--force] \
        [--max-pages 20] \
        [--timeout 30]

The script searches across pages at:
    https://maipark.com/id/corporate/laporan?financePage=N&yearlyPage=1&type=financial
"""

import argparse
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    sync_playwright = None  # type: ignore
    PlaywrightTimeoutError = TimeoutError  # type: ignore


LOGGER = logging.getLogger("download_maipark")
COMPANY_NAME = "PT Reasuransi MAIPARK Indonesia"
COMPANY_ID = "pt_reasuransi_maipark_indonesia"
CATEGORY = "reasuransi"
SOURCE_PAGE_URL_TEMPLATE = "https://maipark.com/id/corporate/laporan?financePage={page}&yearlyPage=1&type=financial"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_PAGES = 20
MANIFEST_TIMEZONE = ZoneInfo("Asia/Jakarta")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

MONTH_NAMES = {
    1: "januari",
    2: "februari",
    3: "maret",
    4: "april",
    5: "mei",
    6: "juni",
    7: "juli",
    8: "agustus",
    9: "september",
    10: "oktober",
    11: "november",
    12: "desember",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download MAIPARK's conventional financial report PDF.",
    )
    parser.add_argument("--year", type=int, required=True, help="Target report year (e.g. 2026).")
    parser.add_argument("--month", type=int, required=True, help="Target report month (1-12).")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data"),
        help="Root output directory (files written to {root}/{YYYY-MM}/maipark/).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Discover without writing PDF.")
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Stop after discovery, write manifest with status=discover_only.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDF.")
    parser.add_argument(
        "--debug-html",
        action="store_true",
        help="Save HTML snapshots when discovery fails.",
    )
    parser.add_argument(
        "--use-browser",
        action="store_true",
        help="Use Playwright for JavaScript-rendered pages.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Maximum pages to search for matching report (default: 20).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> tuple[bool, str]:
    if not 1 <= args.month <= 12:
        return False, "--month must be 1-12"
    if args.year < 1900:
        return False, "--year must be sensible (>= 1900)"
    return True, ""


def _output_dir(output_root: Path, year: int, month: int) -> Path:
    return output_root / f"{year:04d}-{month:02d}" / COMPANY_ID


def _fetch_page_content(page_num: int, timeout: int, use_browser: bool) -> tuple[str | None, str]:
    """Fetch page HTML for a given page number, optionally using browser rendering."""
    url = SOURCE_PAGE_URL_TEMPLATE.format(page=page_num)
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text, "requests"
    except Exception as e:
        LOGGER.debug("requests fetch for page %d failed: %s", page_num, e)
        if not use_browser or sync_playwright is None:
            return None, f"error: {e}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                html = page.content()
                browser.close()
                return html, "playwright"
        except PlaywrightTimeoutError as e:
            LOGGER.debug("playwright timeout on page %d: %s", page_num, e)
            return None, f"playwright_timeout: {e}"
        except Exception as e:
            LOGGER.debug("playwright failed on page %d: %s", page_num, e)
            return None, f"playwright_failed: {e}"


def _extract_reports(html: str, target_year: int, target_month: int) -> list[dict[str, Any]]:
    """Parse HTML and extract financial report links matching year/month."""
    reports = []

    month_name = MONTH_NAMES.get(target_month, "").lower()
    year_str = str(target_year)

    try:
        import json as json_module
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script and script.string:
            data = json_module.loads(script.string)
            reports_list = data.get("props", {}).get("pageProps", {}).get("reports", [])
            for report in reports_list:
                file_name = report.get("fileName", "").lower()
                file_url = report.get("fileUrl", "")

                if month_name in file_name and year_str in file_name and file_url:
                    reports.append({
                        "url": file_url,
                        "text": file_name,
                        "match_score": "high",
                    })
    except Exception as e:
        LOGGER.debug("failed to parse JSON from HTML: %s", e)

    if not reports:
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()

            if not href or not (href.startswith("http") or href.startswith("/")):
                continue
            if ".pdf" not in href.lower():
                continue

            if month_name and month_name in text and year_str in text:
                reports.append({
                    "url": href,
                    "text": text,
                    "match_score": "high" if "laporan keuangan" in text or "financial" in text else "medium",
                })

    return reports


def _get_pagination_info(html: str) -> tuple[int, int]:
    """Extract pagination info from HTML (current page, total pages)."""
    try:
        import json as json_module
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script and script.string:
            data = json_module.loads(script.string)
            paginate = data.get("props", {}).get("pageProps", {}).get("paginate", {})
            current = paginate.get("currentPage", 1)
            total = paginate.get("totalPage", 1)
            return current, total
    except Exception as e:
        LOGGER.debug("failed to extract pagination info: %s", e)
    return 1, 1


def _search_across_pages(target_year: int, target_month: int, timeout: int, use_browser: bool, max_pages: int) -> tuple[dict[str, Any] | None, int]:
    """Search across pages for matching report. Returns (report, page_found)."""
    month_name = MONTH_NAMES.get(target_month, "").lower()

    for page_num in range(1, max_pages + 1):
        LOGGER.info("searching page %d for %s %d", page_num, month_name, target_year)
        html, method = _fetch_page_content(page_num, timeout, use_browser)

        if html is None:
            LOGGER.debug("failed to fetch page %d, skipping", page_num)
            continue

        reports = _extract_reports(html, target_year, target_month)
        if reports:
            LOGGER.info("found matching report on page %d", page_num)
            return reports[0], page_num

        current_page, total_pages = _get_pagination_info(html)
        if current_page >= total_pages:
            LOGGER.debug("reached last page (%d), stopping search", total_pages)
            break

    return None, 0


def _download_file(url: str, output_path: Path, timeout: int, force: bool, dry_run: bool) -> tuple[str, str | None]:
    """Download PDF file and return (status, reason)."""
    if output_path.exists() and not force:
        return "skipped_existing", None

    if dry_run:
        return "discover_only", None

    try:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        resp.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size = output_path.stat().st_size
        LOGGER.info("downloaded %s (%d bytes) -> %s", url, file_size, output_path)
        return "downloaded", None
    except Exception as e:
        LOGGER.error("download failed: %s", e)
        return "error", str(e)


def _write_manifest(records: list[dict[str, Any]], output_dir: Path) -> None:
    """Write manifest files in CSV and JSON formats."""
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "download_manifest.csv"
    json_path = output_dir / "download_manifest.json"

    fields = [
        "category",
        "company_name",
        "source_page_url",
        "target_year",
        "target_month",
        "pdf_url",
        "output_path",
        "status",
        "reason",
        "file_size_bytes",
        "timestamp",
    ]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({k: record.get(k, "") for k in fields})

    with open(json_path, "w") as f:
        json.dump(records, f, indent=2, default=str)

    LOGGER.info("manifest written: %s", csv_path)
    LOGGER.info("manifest written: %s", json_path)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    args = parse_args(argv)

    valid, error = _validate_args(args)
    if not valid:
        LOGGER.error(error)
        return 2

    LOGGER.info(
        "starting maipark download | year=%04d month=%02d dry_run=%s force=%s use_browser=%s max_pages=%d",
        args.year,
        args.month,
        args.dry_run,
        args.force,
        args.use_browser,
        args.max_pages,
    )

    report, page_found = _search_across_pages(args.year, args.month, args.timeout, args.use_browser, args.max_pages)

    if report is None:
        record = {
            "category": CATEGORY,
            "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_PAGE_URL_TEMPLATE.format(page=1),
            "target_year": args.year,
            "target_month": args.month,
            "pdf_url": None,
            "output_path": None,
            "status": "not_found",
            "reason": f"no reports found for {MONTH_NAMES.get(args.month, '?')} {args.year} across {args.max_pages} pages",
            "file_size_bytes": None,
            "timestamp": datetime.now(MANIFEST_TIMEZONE).isoformat(),
        }
        output_dir = _output_dir(args.output_root, args.year, args.month)
        _write_manifest([record], output_dir)
        LOGGER.info("no matching reports found across %d pages", args.max_pages)
        return 1

    LOGGER.info("found report on page %d", page_found)

    pdf_url = report["url"]
    if not pdf_url.startswith("http"):
        from urllib.parse import urljoin
        pdf_url = urljoin(SOURCE_PAGE_URL_TEMPLATE.format(page=page_found), pdf_url)

    if args.discover_only:
        output_dir = _output_dir(args.output_root, args.year, args.month)
        record = {
            "category": CATEGORY,
            "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_PAGE_URL_TEMPLATE.format(page=page_found),
            "target_year": args.year,
            "target_month": args.month,
            "pdf_url": pdf_url,
            "output_path": None,
            "status": "discover_only",
            "reason": None,
            "file_size_bytes": None,
            "timestamp": datetime.now(MANIFEST_TIMEZONE).isoformat(),
        }
        _write_manifest([record], output_dir)
        LOGGER.info("discovery complete (discover-only mode)")
        return 0

    output_dir = _output_dir(args.output_root, args.year, args.month)
    output_path = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    status, reason = _download_file(pdf_url, output_path, args.timeout, args.force, args.dry_run)

    file_size = None
    if output_path.exists():
        file_size = output_path.stat().st_size

    record = {
        "category": CATEGORY,
        "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_PAGE_URL_TEMPLATE.format(page=page_found),
        "target_year": args.year,
        "target_month": args.month,
        "pdf_url": pdf_url,
        "output_path": str(output_path),
        "status": status,
        "reason": reason,
        "file_size_bytes": file_size,
        "timestamp": datetime.now(MANIFEST_TIMEZONE).isoformat(),
    }

    _write_manifest([record], output_dir)

    LOGGER.info("status=%s reason=%s", status, reason or "")
    return 0 if status in {"downloaded", "skipped_existing", "discover_only"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
