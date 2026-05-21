from __future__ import annotations

"""Download Nasre's conventional financial report PDF.

This script is specific to PT Reasuransi Nasional Indonesia and downloads
financial reports from their listing page. Supports discovery-only, dry-run,
browser rendering fallback, and debug HTML snapshots.

Usage:
    python scripts/download/reasuransi/download_nasre.py \
        --year 2026 --month 3 \
        --output-root data \
        [--discover-only] \
        [--use-browser] \
        [--debug-html] \
        [--dry-run] \
        [--force] \
        [--timeout 30]

The script starts from:
    https://nasionalre.id/laporan-tahunan
"""

import argparse
import csv
import json
import logging
import re
import tempfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    sync_playwright = None  # type: ignore
    PlaywrightTimeoutError = TimeoutError  # type: ignore


LOGGER = logging.getLogger("download_nasre")
COMPANY_NAME = "PT Reasuransi Nasional Indonesia"
COMPANY_ID = "pt_reasuransi_nasional_indonesia"
CATEGORY = "reasuransi"
SOURCE_PAGE_URL = "https://nasionalre.id/laporan-tahunan"
DEFAULT_TIMEOUT = 30
MANIFEST_TIMEZONE = ZoneInfo("Asia/Jakarta")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
MONTH_ALIASES: dict[int, tuple[str, ...]] = {
    1: ("januari", "january", "jan"),
    2: ("februari", "february", "feb"),
    3: ("maret", "march", "mar"),
    4: ("april", "apr"),
    5: ("mei", "may"),
    6: ("juni", "june", "jun"),
    7: ("juli", "july", "jul"),
    8: ("agustus", "august", "aug"),
    9: ("september", "sep", "sept"),
    10: ("oktober", "october", "oct", "okt"),
    11: ("november", "nov"),
    12: ("desember", "december", "dec", "des"),
}
SYARIAH_TERMS = ("syariah", "shariah", "sharia", "uus", "islamic", "unit usaha syariah")
REPORT_HINTS = (
    "laporan keuangan",
    "laporan bulanan",
    "financial report",
    "financial statement",
    "publikasi laporan keuangan",
    "report",
    "statement",
)
CONVENTIONAL_HINTS = ("konvensional", "conventional")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Nasre's conventional financial report PDF.")
    parser.add_argument("--year", type=int, required=True, help="Target report year (e.g. 2026).")
    parser.add_argument("--month", type=int, required=True, help="Target report month (1-12).")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data"),
        help="Root output directory (files written to {root}/{YYYY-MM}/nasre/).",
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


def _ascii_fold(value: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_text(value: Any) -> str:
    return _ascii_fold(_clean_text(value)).lower()


def _contains_period(text: str, year: int, month: int) -> bool:
    month2 = f"{month:02d}"
    patterns = (
        rf"(?<!\d){year}[-_/\.]{month2}(?!\d)",
        rf"(?<!\d){year}[-_/\.]{month}(?!\d)",
        rf"(?<!\d){month2}[-_/\.]{year}(?!\d)",
        rf"(?<!\d){month}[-_/\.]{year}(?!\d)",
        rf"(?<!\d){year}{month2}(?!\d)",
        rf"(?<!\d){month2}{year}(?!\d)",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _is_syariah_text(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(term in normalized for term in SYARIAH_TERMS)


def _is_target_period(text: str, year: int, month: int) -> bool:
    normalized = _normalize_text(text)
    if str(year) not in normalized:
        return False
    if _contains_period(normalized, year, month):
        return True
    return any(token in normalized for token in MONTH_ALIASES[month])


def _validate_pdf_bytes(data: bytes) -> bool:
    if len(data) < 16:
        return False
    if not data.startswith(b"%PDF-"):
        return False
    tail = data[-2048:] if len(data) > 2048 else data
    return b"%%EOF" in tail


def _extract_candidates_from_html(html: str, base_url: str, year: int, month: int) -> tuple[list[dict[str, Any]], int, int]:
    """Extract PDF candidates from HTML, returning (candidates, syariah_count, unrelated_count)."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict[str, Any]] = []
    rejected_syariah = 0
    rejected_unrelated = 0
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = _clean_text(anchor.get("href", ""))
        if not href:
            continue

        pdf_url = urljoin(base_url, href)
        if not pdf_url.lower().endswith(".pdf"):
            continue
        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)

        text = _clean_text(anchor.get_text(" ", strip=True))
        blob = _normalize_text(f"{text} {pdf_url}")

        if _is_syariah_text(blob):
            rejected_syariah += 1
            continue
        if not _is_target_period(blob, year, month):
            rejected_unrelated += 1
            continue
        if not any(hint in blob for hint in REPORT_HINTS):
            rejected_unrelated += 1
            continue

        score = 0
        if any(hint in blob for hint in CONVENTIONAL_HINTS):
            score += 200
        if "laporan keuangan" in blob:
            score += 120
        if _contains_period(blob, year, month):
            score += 100
        if blob.endswith(".pdf"):
            score += 50

        candidates.append({
            "pdf_url": pdf_url,
            "text": text,
            "score": score,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, rejected_syariah, rejected_unrelated


def _fetch_page(url: str, timeout: int) -> tuple[str, str]:
    """Fetch page HTML using requests."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text, response.url
    finally:
        session.close()


def _fetch_page_with_browser(url: str, timeout: int) -> tuple[str, str]:
    """Fetch page HTML using Playwright."""
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed; cannot use --use-browser")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=DEFAULT_USER_AGENT)
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            page.wait_for_timeout(500)
            html = page.content()
            final_url = page.url
            return html, final_url
        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"browser timeout: {e}") from e
        finally:
            browser.close()


def _download_file(url: str, output_path: Path, timeout: int, force: bool, dry_run: bool) -> tuple[str, str | None]:
    """Download PDF file and return (status, reason)."""
    if output_path.exists() and not force:
        return "skipped_existing", None

    if dry_run:
        return "discover_only", None

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(output_path.parent), suffix=".part") as tmp:
                temp_path = Path(tmp.name)
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)

        data = temp_path.read_bytes()
        if not _validate_pdf_bytes(data):
            temp_path.unlink(missing_ok=True)
            return "error", "file is not a valid PDF"

        temp_path.replace(output_path)
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
        "starting nasre download | year=%04d month=%02d dry_run=%s force=%s use_browser=%s",
        args.year,
        args.month,
        args.dry_run,
        args.force,
        args.use_browser,
    )

    html = ""
    final_url = SOURCE_PAGE_URL
    syariah_count = 0
    unrelated_count = 0

    try:
        html, final_url = _fetch_page(SOURCE_PAGE_URL, args.timeout)
    except Exception as e:
        LOGGER.debug("static fetch failed: %s", e)
        if args.use_browser:
            try:
                html, final_url = _fetch_page_with_browser(SOURCE_PAGE_URL, args.timeout)
            except Exception as e2:
                LOGGER.error("browser fallback also failed: %s", e2)
                record = {
                    "category": CATEGORY,
                    "company_name": COMPANY_NAME,
                    "source_page_url": SOURCE_PAGE_URL,
                    "target_year": args.year,
                    "target_month": args.month,
                    "pdf_url": None,
                    "output_path": None,
                    "status": "error",
                    "reason": str(e2),
                    "file_size_bytes": None,
                    "timestamp": datetime.now(MANIFEST_TIMEZONE).isoformat(),
                }
                output_dir = _output_dir(args.output_root, args.year, args.month)
                _write_manifest([record], output_dir)
                return 1
        else:
            LOGGER.error("page fetch failed")
            record = {
                "category": CATEGORY,
                "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_PAGE_URL,
                "target_year": args.year,
                "target_month": args.month,
                "pdf_url": None,
                "output_path": None,
                "status": "error",
                "reason": str(e),
                "file_size_bytes": None,
                "timestamp": datetime.now(MANIFEST_TIMEZONE).isoformat(),
            }
            output_dir = _output_dir(args.output_root, args.year, args.month)
            _write_manifest([record], output_dir)
            return 1

    candidates, syariah_count, unrelated_count = _extract_candidates_from_html(html, final_url, args.year, args.month)

    if not candidates:
        record = {
            "category": CATEGORY,
            "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_PAGE_URL,
            "target_year": args.year,
            "target_month": args.month,
            "pdf_url": None,
            "output_path": None,
            "status": "not_found",
            "reason": f"no conventional reports found for {args.month:02d}/{args.year} (syariah={syariah_count}, unrelated={unrelated_count})",
            "file_size_bytes": None,
            "timestamp": datetime.now(MANIFEST_TIMEZONE).isoformat(),
        }
        output_dir = _output_dir(args.output_root, args.year, args.month)
        _write_manifest([record], output_dir)
        LOGGER.info("no matching reports found")
        return 1

    best = candidates[0]
    LOGGER.info("found report with score %d", best["score"])

    if args.discover_only:
        output_dir = _output_dir(args.output_root, args.year, args.month)
        record = {
            "category": CATEGORY,
            "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_PAGE_URL,
            "target_year": args.year,
            "target_month": args.month,
            "pdf_url": best["pdf_url"],
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

    status, reason = _download_file(best["pdf_url"], output_path, args.timeout, args.force, args.dry_run)

    file_size = None
    if output_path.exists():
        file_size = output_path.stat().st_size

    record = {
        "category": CATEGORY,
        "company_name": COMPANY_NAME,
        "source_page_url": SOURCE_PAGE_URL,
        "target_year": args.year,
        "target_month": args.month,
        "pdf_url": best["pdf_url"],
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
