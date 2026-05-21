from __future__ import annotations

"""Download the conventional financial report PDF for Orion Re.

The script starts from https://www.orionre.id/id/publikasi.html, finds the
report PDF for the requested year/month, excludes syariah/sharia/UUS/islamic
documents, validates the PDF payload, writes a manifest, and saves debug HTML
when no matching PDF is found.
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


LOGGER = logging.getLogger("download_orionre_report")

SOURCE_URL = "https://www.orionre.id/id/publikasi.html"
COMPANY_ID = "pt_orion_reasuransi_indonesia"
COMPANY_NAME = "PT Orion Reasuransi Indonesia"
CATEGORY = "reasuransi"
OUTPUT_SUBDIR = "raw_pdf"
DEBUG_HTML_DIRNAME = "_debug_html"

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_PAGES = 1
MAX_RUNTIME_SECONDS = 180
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
    "integrated report",
    "corporate governance",
    "tata kelola",
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


@dataclass(frozen=True)
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
        description="Download the conventional financial report PDF for Orion Re.",
    )
    parser.add_argument("--year", type=positive_int, required=True, help="Target report year.")
    parser.add_argument("--month", type=month_int, required=True, help="Target report month (1-12).")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data"),
        help="Root output directory.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Discover the report without writing the PDF.")
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Stop after discovery, write manifest with status=discover_only.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing PDF.")
    parser.add_argument(
        "--debug-html",
        action="store_true",
        help="Save HTML snapshots when the target PDF cannot be found.",
    )
    parser.add_argument(
        "--use-browser",
        action="store_true",
        help="Use Playwright to render the source page when static HTML is insufficient.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds for page fetch and PDF download requests.",
    )
    args = parser.parse_args(argv)

    if args.timeout < 1:
        parser.error("--timeout must be at least 1")
    return args


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


def target_period_tokens(year: int, month: int) -> list[str]:
    values = [
        f"{year}{month:02d}",
        f"{year}-{month:02d}",
        f"{year}_{month:02d}",
        f"{month:02d}-{year}",
        f"{month:02d}_{year}",
        f"{month:02d}{year}",
    ]
    values.extend(f"{term} {year}" for term in month_terms(month) if not term.isdigit())
    values.extend(f"{year} {term}" for term in month_terms(month) if not term.isdigit())
    return list(dict.fromkeys(values))


def is_syariah_candidate(text: str) -> bool:
    blob = normalize_text(text)
    return bool(blob) and any(re.search(rf"\b{re.escape(term)}\b", blob) for term in SYARIAH_TERMS)


def is_unrelated_candidate(text: str) -> bool:
    blob = normalize_text(text)
    return bool(blob) and any(term in blob for term in UNRELATED_TERMS)


def matches_target_period(text: str, year: int, month: int) -> bool:
    blob = normalize_text(text)
    if not blob:
        return False
    year_hit = re.search(rf"\b{year}\b", blob) is not None
    month_hit = any(re.search(rf"\b{re.escape(term)}\b", blob) for term in month_terms(month))
    token_hit = any(token in blob for token in target_period_tokens(year, month))
    return (year_hit and month_hit) or token_hit


def score_candidate(text: str, year: int, month: int) -> int:
    blob = normalize_text(text)
    score = 0
    if matches_target_period(blob, year, month):
        score += 100
    if blob.endswith(".pdf"):
        score += 10
    if "/publikasi/bulanan/" in blob or "bulanan" in blob:
        score += 20
    if "laporan keuangan" in blob or "financial report" in blob or "financial statement" in blob:
        score += 25
    if "audited" in blob and month == 12:
        score += 10
    return score


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(fragment="").geturl()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.3,
        allowed_methods=frozenset({"GET", "HEAD"}),
        status_forcelist=(429, 500, 502, 503, 504),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_source_html(session: requests.Session, timeout: int) -> tuple[str, str, str]:
    response = session.get(SOURCE_URL, timeout=timeout)
    final_url = canonical_url(response.url)
    content_type = response.headers.get("Content-Type", "")
    html = response.text
    blocked_markers = (
        "please wait while your request is being verified",
        "attention required",
        "cloudflare",
    )
    blob = normalize_text(html)
    if response.status_code >= 400:
        raise RuntimeError(f"source page returned HTTP {response.status_code}")
    if any(marker in blob for marker in blocked_markers):
        raise RuntimeError("source page returned an anti-bot verification page")
    if "text/html" not in content_type.lower() and not html:
        raise RuntimeError(f"unexpected content type for source page: {content_type}")
    return html, final_url, content_type


def render_source_html_with_browser(timeout: int) -> tuple[str, str]:
    if sync_playwright is None:  # pragma: no cover - optional dependency.
        raise RuntimeError("Playwright is not installed; cannot use --use-browser")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            page.goto(SOURCE_URL, wait_until="networkidle", timeout=timeout * 1000)
            page.wait_for_timeout(500)
            html = page.content()
            return html, canonical_url(page.url)
        except PlaywrightTimeoutError as exc:  # pragma: no cover - browser timing varies.
            raise RuntimeError(f"browser timeout while loading {SOURCE_URL}: {exc}") from exc
        except PlaywrightError as exc:  # pragma: no cover - browser timing varies.
            raise RuntimeError(f"browser error while loading {SOURCE_URL}: {exc}") from exc
        finally:
            browser.close()


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    soup = make_soup(html)
    links: list[dict[str, str]] = []
    for tag in soup.find_all("a"):
        href = clean_text(tag.get("href"))
        if not href:
            continue
        absolute_url = canonical_url(urljoin(base_url, href))
        text_parts = [
            clean_text(tag.get_text(" ", strip=True)),
            clean_text(tag.get("title")),
            clean_text(tag.get("aria-label")),
            clean_text(tag.get("download")),
        ]
        parent = tag.parent
        if parent is not None:
            text_parts.append(clean_text(parent.get_text(" ", strip=True)))
        context = clean_text(" ".join(piece for piece in text_parts if piece))
        links.append({"url": absolute_url, "text": context, "raw_href": href})
    return links


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
    target_match = matches_target_period(blob, year, month)
    if is_syariah or is_unrelated or not target_match:
        return None
    return Candidate(
        page_url=page_url,
        discovered_page_url=discovered_page_url,
        pdf_url=canonical_url(url),
        title=text,
        context=text,
        discovery_method=discovery_method,
        score=score_candidate(blob, year, month),
        is_syariah=is_syariah,
        is_unrelated=is_unrelated,
        target_match=target_match,
    )


def extract_candidates_from_html(
    html: str,
    base_url: str,
    year: int,
    month: int,
    discovery_method: str,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for link in extract_links(html, base_url):
        pdf_url = link["url"]
        if not pdf_url.lower().endswith(".pdf"):
            continue
        candidate = build_candidate(
            page_url=SOURCE_URL,
            discovered_page_url=base_url,
            url=pdf_url,
            text=link["text"] or pdf_url,
            year=year,
            month=month,
            discovery_method=discovery_method,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def discover_candidates(
    session: requests.Session,
    year: int,
    month: int,
    *,
    use_browser: bool,
    timeout: int,
) -> tuple[list[Candidate], str, str, str]:
    source_html = ""
    rendered_html = ""
    discovery_method = "static_html"

    static_html = ""
    final_url = SOURCE_URL

    try:
        static_html, final_url, _ = fetch_source_html(session, timeout)
    except Exception as exc:
        if sync_playwright is None:
            raise
        LOGGER.info("static fetch failed, using browser fallback: %s", summarize_exception(exc))
        rendered_html, final_url = render_source_html_with_browser(timeout)
        source_html = rendered_html
        discovery_method = "playwright"
    else:
        final_url = canonical_url(final_url)
        source_html = static_html
        if use_browser or sync_playwright is not None:
            try:
                rendered_html, rendered_final_url = render_source_html_with_browser(timeout)
            except Exception as exc:
                LOGGER.info("browser fallback failed, keeping static HTML: %s", summarize_exception(exc))
            else:
                if rendered_html:
                    final_url = rendered_final_url
                    discovery_method = "playwright"

    active_html = rendered_html or source_html
    candidates = extract_candidates_from_html(active_html, final_url, year, month, discovery_method)
    if not candidates and discovery_method == "static_html" and sync_playwright is not None and not rendered_html:
        try:
            rendered_html, rendered_final_url = render_source_html_with_browser(timeout)
        except Exception as exc:
            LOGGER.info("browser fallback after static parse failed: %s", summarize_exception(exc))
        else:
            if rendered_html:
                source_html = rendered_html
                final_url = rendered_final_url
                discovery_method = "playwright"
                active_html = rendered_html
                candidates = extract_candidates_from_html(active_html, final_url, year, month, discovery_method)

    return candidates, source_html, rendered_html, final_url


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
        with tempfile.NamedTemporaryFile(delete=False, dir=str(output_path.parent), suffix=".part") as tmp:
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


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "download_manifest.csv"
    json_path = output_dir / "download_manifest.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    LOGGER.info("wrote manifest: %s", csv_path)
    LOGGER.info("wrote manifest: %s", json_path)


def write_debug_html(debug_dir: Path, source_html: str, rendered_html: str, reason: str, links: list[dict[str, str]]) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    if source_html:
        (debug_dir / "source_page.html").write_text(source_html, encoding="utf-8")
    if rendered_html and rendered_html != source_html:
        (debug_dir / "rendered_page.html").write_text(rendered_html, encoding="utf-8")
    (debug_dir / "reason.txt").write_text(reason + "\n", encoding="utf-8")
    (debug_dir / "links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_exception(exc: Exception | str) -> str:
    text = str(exc)
    text = text.split("\n", 1)[0]
    return re.sub(r"\s+", " ", text).strip()


def build_no_pdf_reason(
    *,
    year: int,
    month: int,
    source_url: str,
    links: list[dict[str, str]],
    candidates: list[Candidate],
) -> str:
    pdf_links = [link for link in links if link["url"].lower().endswith(".pdf")]
    if not pdf_links:
        return (
            f"no PDF links were found on {source_url} after rendering the source page for "
            f"{year}-{month:02d}"
        )
    if not candidates:
        return (
            f"PDF links were found on {source_url}, but none matched the requested conventional "
            f"report for {year}-{month:02d} after excluding syariah/sharia/UUS/islamic and unrelated "
            "documents"
        )
    syariah_count = sum(1 for item in candidates if item.is_syariah)
    unrelated_count = sum(1 for item in candidates if item.is_unrelated)
    return (
        f"only rejected candidates were discovered for {year}-{month:02d}; "
        f"syariah/sharia/UUS/islamic matches: {syariah_count}; unrelated matches: {unrelated_count}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    start_time = time.monotonic()
    period = f"{args.year:04d}-{args.month:02d}"
    output_dir = args.output_root / period / COMPANY_ID
    output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"
    debug_dir = output_dir / DEBUG_HTML_DIRNAME

    LOGGER.info("starting Orion Re download run for %s", period)
    session = build_session()

    try:
        candidates, source_html, rendered_html, final_url = discover_candidates(
            session,
            args.year,
            args.month,
            use_browser=args.use_browser,
            timeout=args.timeout,
        )
        active_links = extract_links(rendered_html or source_html, final_url)
        best = choose_candidate(candidates)

        if best is None:
            reason = build_no_pdf_reason(
                year=args.year,
                month=args.month,
                source_url=SOURCE_URL,
                links=active_links,
                candidates=candidates,
            )
            write_debug_html(debug_dir, source_html, rendered_html, reason, active_links)
            rows = [
                {
                    "category": CATEGORY,
                    "company_id": COMPANY_ID,
                    "company_name": COMPANY_NAME,
                    "source_page_url": SOURCE_URL,
                    "discovered_page_url": final_url,
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

        http_status, file_size = download_pdf(
            session,
            best.pdf_url,
            output_pdf,
            timeout=args.timeout,
            force=args.force,
        )

        rows = [
            best.to_manifest(
                year=args.year,
                month=args.month,
                output_path=output_pdf,
                status="downloaded" if http_status is not None else "skipped_existing",
                reason=(
                    "downloaded conventional financial report PDF"
                    if http_status is not None
                    else "existing valid PDF was kept"
                ),
                http_status=http_status,
                file_size_bytes=file_size,
                candidate_count=len(candidates),
                rejected_syariah_count=sum(1 for item in candidates if item.is_syariah),
                rejected_unrelated_count=sum(1 for item in candidates if item.is_unrelated),
            )
        ]
        write_manifest(output_dir, rows)

        if args.debug_html:
            write_debug_html(debug_dir, source_html, rendered_html, "download completed", active_links)

        elapsed = time.monotonic() - start_time
        if elapsed > MAX_RUNTIME_SECONDS:
            LOGGER.warning("runtime exceeded soft limit: %.1fs", elapsed)
        LOGGER.info("wrote %s", output_pdf)
        return 0

    except Exception as exc:  # noqa: BLE001
        reason = summarize_exception(exc)
        if args.debug_html:
            try:
                source_html = source_html if "source_html" in locals() else ""
                rendered_html = rendered_html if "rendered_html" in locals() else ""
                active_links = active_links if "active_links" in locals() else []
                write_debug_html(debug_dir, source_html, rendered_html, reason, active_links)
            except Exception:  # pragma: no cover - best effort debug capture.
                LOGGER.exception("failed to write debug HTML")
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
                "status": "error",
                "reason": reason,
                "discovery_method": "playwright" if args.use_browser else "static_html",
                "score": 0,
                "candidate_count": 0,
                "rejected_syariah_count": 0,
                "rejected_unrelated_count": 0,
                "http_status": None,
                "file_size_bytes": None,
                "timestamp": current_timestamp(),
            }
        ]
        write_manifest(output_dir, rows)
        LOGGER.error("failed: %s", reason)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
