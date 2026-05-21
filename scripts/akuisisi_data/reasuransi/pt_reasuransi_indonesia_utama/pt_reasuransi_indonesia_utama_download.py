from __future__ import annotations

"""Download the conventional financial report PDF for Indonesia Re.

This script starts from https://www.indonesiare.co.id/id/investor-relations/financial-report
and downloads only the conventional monthly financial report PDF for the requested year/month.
It excludes syariah/sharia/UUS/islamic documents, writes a manifest, and saves debug HTML
snapshots when the target PDF cannot be found.
"""

import argparse
import csv
import json
import logging
import re
import sys
import tempfile
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:  # pragma: no cover - optional dependency.
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - browser fallback is optional.
    PlaywrightError = Exception  # type: ignore[assignment]
    PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]


LOGGER = logging.getLogger("download_indonesiare_report")

SOURCE_URL = "https://www.indonesiare.co.id/id/investor-relations/financial-report"
COMPANY_ID = "pt_reasuransi_indonesia_utama"
COMPANY_NAME = "PT Reasuransi Indonesia Utama Persero"
CATEGORY = "reasuransi"
OUTPUT_SUBDIR = "raw_pdf"
DEBUG_HTML_DIRNAME = "_debug_html"

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_PAGES = 100  # Indonesia Re has ~21 pages with 4 reports each
DEFAULT_MAX_LINKS_PER_PAGE = 80
MAX_RUNTIME_SECONDS = 300  # Increase runtime for multi-page crawl
MANIFEST_TIMEZONE = ZoneInfo("Asia/Jakarta")

MONTH_NAMES: dict[int, list[str]] = {
    1: ["januari", "january", "jan"],
    2: ["februari", "february", "feb"],
    3: ["maret", "march", "mar"],
    4: ["april", "apr"],
    5: ["mei", "may"],
    6: ["juni", "june", "jun"],
    7: ["juli", "july", "jul"],
    8: ["agustus", "august", "aug"],
    9: ["september", "sep", "sept"],
    10: ["oktober", "october", "oct"],
    11: ["november", "nov"],
    12: ["desember", "december", "dec"],
}

SYARIAH_TERMS = ("syariah", "shariah", "sharia", "uus", "islamic")
UNRELATED_TERMS = (
    "annual report",
    "laporan tahunan",
    "sustainability",
    "keberlanjutan",
    "complaint handling",
    "penanganan pengaduan",
    "whistleblowing",
    "corporate governance",
    "tata kelola",
)
REPORT_TERMS = (
    "laporan keuangan",
    "laporan keuangan bulanan",
    "financial report",
    "financial statement",
    "laporan bulanan",
    "monthly report",
    "monthly financial report",
    "publikasi laporan keuangan",
    "report",
)

MANIFEST_FIELDS = [
    "category",
    "company_id",
    "company_name",
    "source_page_url",
    "discovered_page_url",
    "pdf_url",
    "target_year",
    "target_month",
    "output_path",
    "status",
    "reason",
    "discovery_method",
    "score",
    "candidate_count",
    "rejected_syariah_count",
    "rejected_unrelated_count",
    "http_status",
    "file_size_bytes",
    "timestamp",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


@dataclass
class Candidate:
    page_url: str
    discovered_page_url: str
    pdf_url: str
    title: str
    context: str
    discovery_method: str
    score: int
    is_syariah: bool
    is_unrelated: bool
    target_match: bool

    def to_manifest(
        self,
        *,
        year: int,
        month: int,
        output_path: Path,
        status: str,
        reason: str,
        http_status: int | None,
        file_size_bytes: int | None,
        candidate_count: int,
        rejected_syariah_count: int,
        rejected_unrelated_count: int,
    ) -> dict[str, Any]:
        return {
            "category": CATEGORY,
            "company_id": COMPANY_ID,
            "company_name": COMPANY_NAME,
            "source_page_url": SOURCE_URL,
            "discovered_page_url": self.discovered_page_url,
            "pdf_url": self.pdf_url,
            "target_year": year,
            "target_month": month,
            "output_path": str(output_path),
            "status": status,
            "reason": reason,
            "discovery_method": self.discovery_method,
            "score": self.score,
            "candidate_count": candidate_count,
            "rejected_syariah_count": rejected_syariah_count,
            "rejected_unrelated_count": rejected_unrelated_count,
            "http_status": http_status,
            "file_size_bytes": file_size_bytes,
            "timestamp": current_timestamp(),
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the conventional financial report PDF for Indonesia Re.",
    )
    parser.add_argument(
        "--year",
        type=positive_int,
        required=True,
        help="Target report year.",
    )
    parser.add_argument(
        "--month",
        type=month_int,
        required=True,
        help="Target report month (1-12).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data"),
        help="Root output directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover the report without writing the PDF.",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Stop after discovery, write manifest with status=discover_only.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing PDF.",
    )
    parser.add_argument(
        "--debug-html",
        action="store_true",
        help="Save HTML snapshots when the target PDF cannot be found.",
    )
    parser.add_argument(
        "--use-browser",
        action="store_true",
        help="Use Playwright to render the page when static HTML is insufficient.",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=30,
        help="HTTP request timeout in seconds.",
    )
    return parser.parse_args(argv)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def month_int(value: str) -> int:
    parsed = positive_int(value)
    if parsed > 12:
        raise argparse.ArgumentTypeError("month must be between 1 and 12")
    return parsed


def ascii_fold(value: str | Any) -> str:
    normalized = unicodedata.normalize("NFKD", str("" if value is None else value))
    return normalized.encode("ascii", "ignore").decode("ascii")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "none"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", ascii_fold(clean_text(value))).strip().lower()


def make_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")


def current_timestamp() -> str:
    return datetime.now(MANIFEST_TIMEZONE).isoformat(timespec="seconds")


def month_terms(month: int) -> list[str]:
    terms = list(MONTH_NAMES[month])
    terms.extend([f"{month:02d}", str(month)])
    return list(dict.fromkeys(terms))


def target_period_text(year: int, month: int) -> list[str]:
    terms = month_terms(month)
    values = [
        f"{year}-{month:02d}",
        f"{year}_{month:02d}",
        f"{month:02d}-{year}",
        f"{month:02d}_{year}",
        f"{year}{month:02d}",
        f"{month:02d}{year}",
    ]
    values.extend(f"{term} {year}" for term in terms if not term.isdigit())
    values.extend(f"{year} {term}" for term in terms if not term.isdigit())
    return list(dict.fromkeys(values))


def is_syariah_candidate(text: str) -> bool:
    blob = normalize_text(text)
    if not blob:
        return False
    return any(re.search(rf"\b{re.escape(term)}\b", blob) for term in SYARIAH_TERMS)


def is_unrelated_candidate(text: str) -> bool:
    blob = normalize_text(text)
    if not blob:
        return False
    return any(term in blob for term in UNRELATED_TERMS)


def is_reportish(text: str) -> bool:
    blob = normalize_text(text)
    if not blob:
        return False
    return any(term in blob for term in REPORT_TERMS)


def matches_target_period(text: str, year: int, month: int) -> bool:
    blob = normalize_text(text)
    if not blob:
        return False
    month_hit = any(re.search(rf"\b{re.escape(term)}\b", blob) for term in month_terms(month))
    year_hit = re.search(rf"\b{year}\b", blob) is not None
    numeric_hit = any(re.search(rf"\b{re.escape(term)}\b", blob) for term in target_period_text(year, month))

    previous_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_month_hit = any(re.search(rf"\bper\s+{re.escape(term)}\b", blob) for term in month_terms(previous_month))
    prev_year_hit = re.search(rf"\b{prev_year}\b", blob) is not None

    return (month_hit and year_hit) or numeric_hit or (prev_month_hit and prev_year_hit)


def positive_score(text: str, year: int, month: int) -> int:
    blob = normalize_text(text)
    score = 0

    month_hit = any(re.search(rf"\b{re.escape(term)}\b", blob) for term in month_terms(month))
    year_hit = re.search(rf"\b{year}\b", blob) is not None
    numeric_hit = any(re.search(rf"\b{re.escape(term)}\b", blob) for term in target_period_text(year, month))
    exact_match = (month_hit and year_hit) or numeric_hit

    previous_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_month_hit = any(re.search(rf"\bper\s+{re.escape(term)}\b", blob) for term in month_terms(previous_month))
    prev_year_hit = re.search(rf"\b{prev_year}\b", blob) is not None
    prev_match = prev_month_hit and prev_year_hit

    if exact_match:
        score += 70
    elif prev_match:
        score += 40

    is_report = is_reportish(blob)
    if is_report:
        score += 25
    is_conventional = "laporan keuangan konvensional" in blob or "laporan keuangan perusahaan" in blob
    if is_conventional:
        score += 30
    is_pdf = blob.endswith(".pdf")
    if is_pdf:
        score += 10
    return score


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(fragment="").geturl()


def summarize_exception(exc: Exception | str) -> str:
    text = str(exc)
    text = text.split("\n", 1)[0]
    return re.sub(r"\s+", " ", text).strip()


def html_title_and_text(html: str) -> tuple[str, str]:
    soup = make_soup(html)
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    text = clean_text(soup.get_text(" ", strip=True))
    return title, text


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    soup = make_soup(html)
    links: list[dict[str, str]] = []
    for tag in soup.find_all(["a", "button"]):
        href = clean_text(tag.get("href"))
        if not href and tag.name != "button":
            continue
        if tag.name == "button" and not href:
            continue
        url = urljoin(base_url, href)
        text_parts = [
            clean_text(tag.get_text(" ", strip=True)),
            clean_text(tag.get("title")),
            clean_text(tag.get("aria-label")),
            clean_text(tag.get("data-title")),
            clean_text(tag.get("download")),
        ]
        parent = tag.parent
        while parent is not None:
            parent_name = getattr(parent, "name", "")
            if parent_name in {"body", "html"}:
                break
            parent_text = clean_text(parent.get_text(" ", strip=True))
            if 0 < len(parent_text) <= 300:
                text_parts.append(parent_text)
                break
            parent = parent.parent
        context = clean_text(" ".join(piece for piece in text_parts if piece))
        links.append(
            {
                "url": canonical_url(url),
                "text": context,
                "raw_href": href,
            }
        )
    return links[:DEFAULT_MAX_LINKS_PER_PAGE]


def same_domain(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.lower() == urlparse(url_b).netloc.lower()


def is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def fetch_html(session: requests.Session, url: str, timeout: int) -> tuple[str, str, int, str]:
    response = session.get(url, timeout=timeout)
    status = response.status_code
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    html = response.text
    return html, canonical_url(response.url), status, content_type


def render_html_with_browser(url: str, timeout: int, year: int) -> tuple[str, str]:
    if sync_playwright is None:  # pragma: no cover - optional dependency.
        raise RuntimeError("Playwright is not installed; cannot use --use-browser")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 2200},
        )
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            for label in ("FINANCIAL REPORT", "LAPORAN KEUANGAN", str(year)):
                try:
                    page.get_by_text(label, exact=False).first.click(timeout=1500)
                except Exception:
                    pass
            page.wait_for_timeout(500)
            html = page.content()
            final_url = canonical_url(page.url)
            return html, final_url
        except PlaywrightTimeoutError as exc:  # pragma: no cover - browser timing varies.
            raise RuntimeError(f"browser timeout while loading {url}: {exc}") from exc
        except PlaywrightError as exc:  # pragma: no cover - browser timing varies.
            raise RuntimeError(f"browser error while loading {url}: {exc}") from exc
        finally:
            browser.close()


def build_candidate(
    *,
    page_url: str,
    discovered_page_url: str,
    url: str,
    text: str,
    year: int,
    month: int,
    discovery_method: str,
) -> Candidate | None:
    blob = f"{text} {url}"
    is_syariah = is_syariah_candidate(blob)
    is_unrelated = is_unrelated_candidate(blob)
    target_match = matches_target_period(text, year, month)
    if is_syariah or is_unrelated or not target_match:
        return None
    score = positive_score(blob, year, month)
    return Candidate(
        page_url=page_url,
        discovered_page_url=discovered_page_url,
        pdf_url=canonical_url(url),
        title=text,
        context=text,
        discovery_method=discovery_method,
        score=score,
        is_syariah=is_syariah,
        is_unrelated=is_unrelated,
        target_match=target_match,
    )


def discover_candidates(
    session: requests.Session,
    source_url: str,
    year: int,
    month: int,
    *,
    use_browser: bool,
    timeout: int,
    max_pages: int,
    max_depth: int,
    deadline: float,
) -> tuple[list[Candidate], list[dict[str, str]], str, str]:
    visited: set[str] = set()
    queue: deque[tuple[str, int, str]] = deque([(source_url, 0, "static_html")])
    candidates: list[Candidate] = []
    snapshots: list[dict[str, str]] = []
    source_html = ""
    rendered_html = ""

    while queue and len(visited) < max_pages and time.monotonic() < deadline:
        current_url, depth, discovery_method = queue.popleft()
        current_url = canonical_url(current_url)
        if current_url in visited:
            continue
        visited.add(current_url)

        html = ""
        final_url = current_url
        content_type = ""
        fetch_error: str | None = None

        try:
            html, final_url, _, content_type = fetch_html(session, current_url, timeout)
        except Exception as exc:
            fetch_error = summarize_exception(exc)
            if use_browser:
                try:
                    html, final_url = render_html_with_browser(current_url, timeout, year)
                    discovery_method = "playwright"
                except Exception as browser_exc:
                    fetch_error = (
                        f"{fetch_error}; browser fallback failed: "
                        f"{summarize_exception(browser_exc)}"
                    )
            else:
                raise

        if not source_html and final_url == canonical_url(source_url):
            source_html = html

        if discovery_method == "playwright" and not rendered_html:
            rendered_html = html

        title, _page_text = html_title_and_text(html)
        if html and current_url == canonical_url(source_url):
            snapshots.append(
                {
                    "url": final_url,
                    "title": title,
                    "content_type": content_type,
                    "method": discovery_method,
                    "error": fetch_error or "",
                }
            )

        for link in extract_links(html, final_url):
            link_url = link["url"]
            link_text = link["text"]
            if not link_url:
                continue
            if is_pdf_url(link_url):
                candidate = build_candidate(
                    page_url=current_url,
                    discovered_page_url=final_url,
                    url=link_url,
                    text=link_text or title,
                    year=year,
                    month=month,
                    discovery_method=discovery_method,
                )
                if candidate is not None:
                    candidates.append(candidate)
                continue
            # Follow pagination and other same-domain links
            if depth < max_depth and same_domain(link_url, source_url):
                # Check if it looks like a pagination link or navigation
                link_url_lower = link_url.lower()
                link_text_lower = normalize_text(link_text)
                is_pagination = (
                    "page=" in link_url_lower or
                    any(term in link_text_lower for term in ["page", "next", "previous", "prev", ">", "<"])
                )
                if is_pagination or "financial" in link_text_lower or "laporan" in link_text_lower:
                    queue.append((link_url, depth + 1, discovery_method))

    if use_browser and not rendered_html and source_html:
        rendered_html = source_html

    return candidates, snapshots, source_html, rendered_html


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    best_by_url: dict[str, Candidate] = {}
    for candidate in candidates:
        current = best_by_url.get(candidate.pdf_url)
        if current is None or candidate.score > current.score:
            best_by_url[candidate.pdf_url] = candidate
    return sorted(best_by_url.values(), key=lambda item: item.score, reverse=True)


def choose_candidate(candidates: list[Candidate]) -> Candidate | None:
    filtered = dedupe_candidates(candidates)
    return filtered[0] if filtered else None


def validate_pdf_bytes(data: bytes) -> bool:
    if len(data) < 16:
        return False
    if not data.startswith(b"%PDF-"):
        return False
    tail = data[-2048:] if len(data) > 2048 else data
    return b"%%EOF" in tail


def download_pdf(
    session: requests.Session,
    pdf_url: str,
    output_path: Path,
    *,
    timeout: int,
    force: bool,
) -> tuple[int | None, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        existing = output_path.read_bytes()
        if validate_pdf_bytes(existing):
            return None, len(existing)

    with session.get(pdf_url, timeout=timeout, stream=True) as response:
        status = response.status_code
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=str(output_path.parent),
            suffix=".part",
        ) as tmp:
            temp_path = Path(tmp.name)
            try:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
            finally:
                tmp.flush()

    data = temp_path.read_bytes()
    if "pdf" not in content_type and not validate_pdf_bytes(data):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file from {pdf_url} is not a valid PDF")
    if not validate_pdf_bytes(data):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file from {pdf_url} failed PDF validation")

    temp_path.replace(output_path)
    return status, len(data)


def build_no_pdf_reason(
    *,
    candidates: list[Candidate],
    snapshots: list[dict[str, str]],
    year: int,
    month: int,
    source_url: str,
) -> str:
    if not candidates:
        if snapshots:
            available = ", ".join(snapshot["url"] for snapshot in snapshots[:3])
            return (
                f"no conventional monthly financial report PDF for {year}-{month:02d} was found on {source_url}; "
                f"the page was fetched successfully, but no link matched the requested month/year "
                f"after excluding syariah/sharia/UUS/islamic and unrelated report categories. "
                f"Visited pages: {available}"
            )
        return (
            f"no conventional monthly financial report PDF for {year}-{month:02d} was found on {source_url}; "
            "the page could not be rendered into any candidate links."
        )

    syariah_count = sum(1 for item in candidates if item.is_syariah)
    unrelated_count = sum(1 for item in candidates if item.is_unrelated)
    return (
        f"only rejected candidates were discovered for {year}-{month:02d}; "
        "syariah/sharia/UUS/islamic matches: "
        f"{syariah_count}; unrelated matches: {unrelated_count}."
    )


def write_debug_html(
    debug_dir: Path,
    source_html: str,
    rendered_html: str,
    reason: str,
    snapshots: list[dict[str, str]],
) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    if source_html:
        (debug_dir / "source_page.html").write_text(source_html, encoding="utf-8")
    if rendered_html and rendered_html != source_html:
        (debug_dir / "rendered_page.html").write_text(rendered_html, encoding="utf-8")
    (debug_dir / "reason.txt").write_text(reason + "\n", encoding="utf-8")
    (debug_dir / "snapshots.json").write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "download_manifest.csv"
    json_path = output_dir / "download_manifest.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = (
        args.output_root
        / f"{args.year:04d}-{args.month:02d}"
        / "reasuransi"
        / COMPANY_ID
    )
    debug_dir = output_dir / DEBUG_HTML_DIRNAME
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"

    deadline = time.monotonic() + MAX_RUNTIME_SECONDS
    session = build_session()

    LOGGER.info("starting discovery from %s", SOURCE_URL)
    candidates: list[Candidate] = []
    snapshots: list[dict[str, str]] = []
    source_html = ""
    rendered_html = ""
    discovery_error: str | None = None

    try:
        candidates, snapshots, source_html, rendered_html = discover_candidates(
            session,
            SOURCE_URL,
            args.year,
            args.month,
            use_browser=args.use_browser,
            timeout=args.timeout,
            max_pages=DEFAULT_MAX_PAGES,
            max_depth=DEFAULT_MAX_PAGES,
            deadline=deadline,
        )
    except Exception as exc:
        discovery_error = summarize_exception(exc)
        LOGGER.error("discovery failed: %s", discovery_error)

    best = choose_candidate(candidates)
    if best is None:
        reason = discovery_error or build_no_pdf_reason(
            candidates=candidates,
            snapshots=snapshots,
            year=args.year,
            month=args.month,
            source_url=SOURCE_URL,
        )
        write_debug_html(debug_dir, source_html, rendered_html, reason, snapshots)
        rows = [
            {
                "category": CATEGORY,
                "company_id": COMPANY_ID,
                "company_name": COMPANY_NAME,
                "source_page_url": SOURCE_URL,
                "discovered_page_url": SOURCE_URL,
                "pdf_url": "",
                "target_year": args.year,
                "target_month": args.month,
                "output_path": str(output_pdf),
                "status": "not_found",
                "reason": reason,
                "discovery_method": "playwright" if args.use_browser else "static_html",
                "score": 0,
                "candidate_count": len(candidates),
                "rejected_syariah_count": sum(1 for item in candidates if item.is_syariah),
                "rejected_unrelated_count": sum(1 for item in candidates if item.is_unrelated),
                "http_status": None,
                "file_size_bytes": None,
                "timestamp": current_timestamp(),
            }
        ]
        write_manifest(output_dir, rows)
        LOGGER.error(reason)
        return 1

    if args.discover_only:
        reason = "discovery completed; download skipped by --discover-only"
        rows = [
            best.to_manifest(
                year=args.year,
                month=args.month,
                output_path=output_pdf,
                status="discover_only",
                reason=reason,
                http_status=None,
                file_size_bytes=None,
                candidate_count=len(candidates),
                rejected_syariah_count=sum(1 for item in candidates if item.is_syariah),
                rejected_unrelated_count=sum(1 for item in candidates if item.is_unrelated),
            )
        ]
        write_manifest(output_dir, rows)
        LOGGER.info("%s", reason)
        return 0

    if args.dry_run:
        reason = "dry-run requested; PDF discovery completed without writing the file"
        rows = [
            best.to_manifest(
                year=args.year,
                month=args.month,
                output_path=output_pdf,
                status="dry_run",
                reason=reason,
                http_status=None,
                file_size_bytes=None,
                candidate_count=len(candidates),
                rejected_syariah_count=sum(1 for item in candidates if item.is_syariah),
                rejected_unrelated_count=sum(1 for item in candidates if item.is_unrelated),
            )
        ]
        write_manifest(output_dir, rows)
        LOGGER.info("%s", reason)
        return 0

    try:
        http_status, file_size = download_pdf(
            session,
            best.pdf_url,
            output_pdf,
            timeout=args.timeout,
            force=args.force,
        )
    except Exception as exc:
        reason = f"failed to download PDF: {summarize_exception(exc)}"
        if args.debug_html:
            write_debug_html(debug_dir, source_html, rendered_html, reason, snapshots)
        rows = [
            best.to_manifest(
                year=args.year,
                month=args.month,
                output_path=output_pdf,
                status="error",
                reason=reason,
                http_status=None,
                file_size_bytes=None,
                candidate_count=len(candidates),
                rejected_syariah_count=sum(1 for item in candidates if item.is_syariah),
                rejected_unrelated_count=sum(1 for item in candidates if item.is_unrelated),
            )
        ]
        write_manifest(output_dir, rows)
        LOGGER.error(reason)
        return 1

    if args.debug_html and not output_pdf.exists():
        write_debug_html(debug_dir, source_html, rendered_html, "download completed", snapshots)

    rows = [
        best.to_manifest(
            year=args.year,
            month=args.month,
            output_path=output_pdf,
            status="downloaded" if http_status is not None else "skipped_existing",
            reason="downloaded conventional financial report PDF"
            if http_status is not None
            else "existing valid PDF was kept",
            http_status=http_status,
            file_size_bytes=file_size,
            candidate_count=len(candidates),
            rejected_syariah_count=sum(1 for item in candidates if item.is_syariah),
            rejected_unrelated_count=sum(1 for item in candidates if item.is_unrelated),
        )
    ]
    write_manifest(output_dir, rows)
    LOGGER.info("wrote %s", output_pdf)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
