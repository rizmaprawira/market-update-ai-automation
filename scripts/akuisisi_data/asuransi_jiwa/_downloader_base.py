"""Base downloader for life insurance company financial reports."""
import csv
import json
import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None

LOGGER = logging.getLogger("downloader_base")

MONTH_NAMES = {
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

MONTH_LABELS = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

REPORT_KEYWORDS = (
    "laporan keuangan konvensional",
    "laporan keuangan perusahaan",
    "laporan keuangan",
    "financial report",
    "financial statement",
    "monthly financial statement",
    "monthly report",
    "laporan bulanan",
    "publikasi laporan keuangan",
    "published report",
    "report",
    "laporan",
    "financial",
    "download",
    "unduh",
)

REPORT_CONTROL_KEYWORDS = (
    "laporan keuangan",
    "financial report",
    "financial statement",
    "laporan bulanan",
    "monthly report",
    "monthly financial statement",
    "laporan tahunan",
    "annual report",
    "report",
    "download",
    "unduh",
    "cari laporan",
)

CONVENTIONAL_TERMS = (
    "konvensional",
    "conventional",
    "non syariah",
    "non-sharia",
    "non sharia",
)

SYARIAH_TERMS = (
    "syariah",
    "sharia",
    "shariah",
    "unit syariah",
    "usaha syariah",
    "uuss",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

MANIFEST_TIMEZONE = ZoneInfo("Asia/Jakarta")
MANIFEST_FIELDS = [
    "category", "company_id", "company_name", "source_page_url", 
    "discovered_page_url", "pdf_url", "target_year", "target_month",
    "output_path", "status", "reason", "discovery_method", "score",
    "candidate_count", "http_status", "file_size_bytes", "timestamp"
]

@dataclass(frozen=True)
class PDFCandidate:
    url: str
    text: str
    score: int
    discovered_url: str


def is_probable_pdf_url(url):
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    return (
        path.endswith(".pdf")
        or ".pdf" in path
        or "download=true" in query
        or "view=true" in query
    )

def current_timestamp():
    return datetime.now(MANIFEST_TIMEZONE).isoformat(timespec="seconds")

def build_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.3,
                  status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def normalize_text(text):
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def _has_any_term(blob, terms):
    return any(term in blob for term in terms)

def _report_period_terms(year, month):
    terms = [
        str(year),
        f"{year}-{month:02d}",
        f"{year} {month:02d}",
        MONTH_LABELS[month].lower(),
    ]
    terms.extend(MONTH_NAMES[month])
    return list(dict.fromkeys(terms))

def _looks_conventional(blob):
    return _has_any_term(blob, CONVENTIONAL_TERMS) or not _has_any_term(blob, SYARIAH_TERMS)

def _looks_syariah_only(blob):
    return _has_any_term(blob, SYARIAH_TERMS) and not _has_any_term(blob, CONVENTIONAL_TERMS)

def month_terms(month):
    terms = list(MONTH_NAMES[month])
    terms.extend([f"{month:02d}", str(month)])
    return list(dict.fromkeys(terms))

def matches_target_period(text, year, month):
    blob = normalize_text(text)
    if not blob:
        return False
    month_hit = any(re.search(rf'(?<![a-z]){re.escape(term)}(?![a-z])', blob) for term in month_terms(month))
    year_hit = re.search(rf'(?<!\d){year}(?!\d)', blob) is not None
    return month_hit and year_hit

def score_candidate(text, year, month):
    blob = normalize_text(text)
    score = 0
    if matches_target_period(blob, year, month):
        score += 50
    if "laporan" in blob and "keuangan" in blob:
        score += 30
    if "bulanan" in blob or "monthly" in blob:
        score += 20
    if blob.endswith("pdf"):
        score += 10
    return score

def extract_pdf_links(html, base_url, year, month):
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []
    
    for link in soup.find_all('a'):
        href = link.get('href', '').strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        
        text = link.get_text(strip=True)
        parent_text = ""
        if link.parent:
            parent_text = link.parent.get_text(" ", strip=True)
        grandparent_text = ""
        if link.parent and link.parent.parent:
            grandparent_text = link.parent.parent.get_text(" ", strip=True)
        title = link.get("title", "").strip()
        aria_label = link.get("aria-label", "").strip()
        download_attr = link.get("download", "").strip()
        link_blob = " ".join(part for part in [text, href, title, aria_label, download_attr] if part)
        blob_text = " ".join(part for part in [link_blob, parent_text, grandparent_text] if part)
        normalized_link = normalize_text(link_blob)
        url = urljoin(base_url, href)
        if not (href.lower().endswith(".pdf") or is_probable_pdf_url(url)):
            continue
        if _looks_syariah_only(normalized_link):
            continue
        
        if matches_target_period(blob_text + " " + url, year, month):
            score = score_candidate(blob_text + " " + url, year, month)
            if _has_any_term(normalized_link, CONVENTIONAL_TERMS):
                score += 10
            candidates.append(PDFCandidate(url=url, text=text, score=score, discovered_url=base_url))
    
    return sorted(candidates, key=lambda x: x.score, reverse=True)


def extract_report_links(html, base_url, year, month):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    keywords = REPORT_KEYWORDS
    period_terms = _report_period_terms(year, month)
    parsed_base = urlparse(base_url)
    download_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    for link in soup.find_all("a"):
        href = link.get("href", "").strip()
        data_folder = link.get("data-folder", "").strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            if not data_folder:
                continue
        text = link.get_text(" ", strip=True)
        parent_text = ""
        if link.parent:
            parent_text = link.parent.get_text(" ", strip=True)
        grandparent_text = ""
        if link.parent and link.parent.parent:
            grandparent_text = link.parent.parent.get_text(" ", strip=True)
        title = link.get("title", "").strip()
        aria_label = link.get("aria-label", "").strip()
        onclick = link.get("onclick", "").strip()
        link_blob = " ".join(part for part in [text, href, data_folder, title, aria_label, onclick] if part)
        context_blob = " ".join(part for part in [parent_text, grandparent_text] if part)
        blob = " ".join(part for part in [link_blob, context_blob] if part)
        normalized = normalize_text(blob)
        normalized_link = normalize_text(link_blob)
        if _looks_syariah_only(normalized_link):
            continue
        if not any(keyword in normalized for keyword in keywords):
            continue
        if not (
            matches_target_period(blob, year, month)
            or any(term in normalized for term in period_terms)
            or str(year) in normalized
        ):
            continue
        if data_folder:
            url = f"{download_origin}/admin/bli/apt/myfile/download_file_s3/{quote(data_folder, safe='/')}"
        else:
            url = urljoin(base_url, href)
        score = score_candidate(blob, year, month) + 5
        if _has_any_term(normalized_link, CONVENTIONAL_TERMS):
            score += 15
        if _looks_syariah_only(normalized_link):
            score -= 200
        if is_probable_pdf_url(url):
            score += 25
        candidates.append(PDFCandidate(url=url, text=text or href, score=score, discovered_url=base_url))
    return sorted(candidates, key=lambda x: x.score, reverse=True)


def _select_report_filters(page, year, month):
    month_label = MONTH_LABELS[month]
    selects = page.locator("select")
    count = selects.count()
    selected_month = False
    selected_year = False

    for index in range(count):
        select = selects.nth(index)
        option_texts = select.evaluate(
            """(node) => Array.from(node.options).map((option) => (option.textContent || '').trim())"""
        )
        option_blob = " ".join(option_texts).lower()

        if not selected_month and month_label.lower() in option_blob:
            try:
                select.select_option(label=month_label)
                selected_month = True
                continue
            except Exception:
                pass

        if not selected_year and str(year) in option_blob:
            try:
                select.select_option(label=str(year))
                selected_year = True
                page.wait_for_timeout(250)
                continue
            except Exception:
                pass

        if any(label in option_blob for label in ("konvensional", "tahunan", "triwulan", "monthly", "financial")):
            for label in ("Konvensional", "Conventional", "Tahunan"):
                try:
                    select.select_option(label=label)
                    page.wait_for_timeout(250)
                    break
                except Exception:
                    continue

    for label in ("Laporan Keuangan", "Laporan Kinerja Bulanan", "Laporan Tahunan"):
        for role in ("tab", "button", "link"):
            try:
                page.get_by_role(role, name=re.compile(label, re.I)).first.click(timeout=1000)
                page.wait_for_timeout(400)
                break
            except Exception:
                try:
                    page.get_by_text(label, exact=False).first.click(timeout=1000)
                    page.wait_for_timeout(400)
                    break
                except Exception:
                    continue


def _control_blob(element):
    return element.evaluate(
        """(node) => {
            const parts = [];
            if (node.innerText) parts.push(node.innerText);
            if (node.textContent) parts.push(node.textContent);
            for (const attr of ['title', 'aria-label', 'href', 'data-href', 'data-url', 'data-link', 'download', 'value', 'onclick']) {
                const value = node.getAttribute ? node.getAttribute(attr) : '';
                if (value) parts.push(value);
            }
            return parts.join(' ');
        }"""
    )


def _looks_like_pdf_response(response):
    try:
        url = normalize_text(response.url)
    except Exception:
        url = ""
    try:
        headers = response.headers or {}
    except Exception:
        headers = {}
    content_type = normalize_text(headers.get("content-type", ""))
    content_disposition = normalize_text(headers.get("content-disposition", ""))
    return (
        "application/pdf" in content_type
        or url.endswith(".pdf")
        or ".pdf" in url
        or "pdf" in content_disposition
        or "attachment" in content_disposition and "filename" in content_disposition and "pdf" in content_disposition
    )


def _augment_html_with_pdf_hints(html, pdf_hints):
    if not pdf_hints:
        return html
    hint_links = "\n".join(
        f'<a href="{hint}" data-hint="browser-pdf">{hint}</a>'
        for hint in dict.fromkeys(pdf_hints)
        if hint
    )
    if "</body>" in html:
        return html.replace("</body>", f"{hint_links}</body>", 1)
    return html + hint_links


def _click_report_controls(page, year, month):
    terms = _report_period_terms(year, month) + list(REPORT_CONTROL_KEYWORDS) + list(CONVENTIONAL_TERMS)
    selectors = "button, a[href], [role='button'], summary, [aria-expanded], [data-href], [data-url], [data-link], [onclick]"
    locator = page.locator(selectors)
    changed = False
    count = min(locator.count(), 120)

    for index in range(count):
        element = locator.nth(index)
        try:
            if not element.is_visible():
                continue
        except Exception:
            continue

        try:
            blob = normalize_text(_control_blob(element))
        except Exception:
            continue

        if not blob or _looks_syariah_only(blob):
            continue
        if not any(term in blob for term in terms):
            continue
        if is_probable_pdf_url(blob):
            continue

        try:
            element.click(timeout=1500)
            page.wait_for_timeout(600)
            changed = True
        except Exception:
            continue

    return changed


def _stabilize_browser_page(page, timeout):
    page.wait_for_timeout(min(1500, max(500, timeout * 20)))
    for _ in range(3):
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            page.evaluate("window.scrollTo(document.body.scrollWidth, document.body.scrollHeight)")
            page.wait_for_timeout(300)
            page.evaluate("window.scrollTo(document.body.scrollWidth, 0)")
            page.wait_for_timeout(300)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
        except Exception:
            break
    try:
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(250)
        page.mouse.wheel(0, -1200)
        page.wait_for_timeout(250)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=min(5000, timeout * 500))
    except Exception:
        pass


def _goto_with_fallback(page, url, timeout):
    last_error = None
    for wait_until in ("domcontentloaded", "commit"):
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout * 1000)
            return
        except PlaywrightTimeoutError as e:
            last_error = e
            continue
    raise PlaywrightTimeoutError(str(last_error) if last_error else "page load timed out")


def fetch_html_browser_report(url, timeout, year, month):
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        pdf_hints = []

        def remember_response(response):
            try:
                if _looks_like_pdf_response(response):
                    pdf_hints.append(response.url)
            except Exception:
                pass

        page.on("response", remember_response)
        try:
            _goto_with_fallback(page, url, timeout)
            for _ in range(3):
                _stabilize_browser_page(page, timeout)
                changed = _select_report_filters(page, year, month)
                changed = _click_report_controls(page, year, month) or changed
                try:
                    page.get_by_role("button", name=re.compile(r"cari laporan", re.I)).first.click(timeout=1500)
                    changed = True
                except Exception:
                    try:
                        page.get_by_text(re.compile(r"cari laporan", re.I), exact=False).first.click(timeout=1500)
                        changed = True
                    except Exception:
                        pass
                if not changed:
                    break
                _stabilize_browser_page(page, timeout)
            html = page.content()
            final_url = page.url
            return _augment_html_with_pdf_hints(html, pdf_hints), final_url, list(dict.fromkeys(pdf_hints))
        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"browser timeout: {e}") from e
        except PlaywrightError as e:
            raise RuntimeError(f"browser error: {e}") from e
        finally:
            browser.close()


def discover_download_candidate(session, html, base_url, year, month, timeout=30, max_depth=2):
    visited = set()
    queue = [PDFCandidate(url=base_url, text="", score=0, discovered_url=base_url)]

    while queue and len(visited) <= max_depth * 20:
        current = queue.pop(0)
        if current.url in visited:
            continue
        visited.add(current.url)

        if is_probable_pdf_url(current.url):
            return PDFCandidate(url=current.url, text=current.text or current.url, score=current.score, discovered_url=current.discovered_url)

        if current.url == base_url:
            current_html = html
            current_base = base_url
        else:
            current_html = ""
            current_base = current.url
            fetch_errors = []
            for fetcher in (
                lambda: fetch_html_static(session, current.url, timeout),
                lambda: fetch_html_browser_report(current.url, timeout, year, month),
                lambda: fetch_html_browser_domready(current.url, timeout),
            ):
                try:
                    response_html, current_base = fetcher()
                    current_html = response_html
                    break
                except Exception as exc:
                    fetch_errors.append(str(exc))
            if not current_html:
                LOGGER.debug("unable to fetch %s while discovering report links: %s", current.url, "; ".join(fetch_errors))
                continue

        direct_candidates = extract_pdf_links(current_html, current_base, year, month)
        if direct_candidates:
            return direct_candidates[0]

        follow_candidates = extract_report_links(current_html, current_base, year, month)
        for candidate in follow_candidates:
            if candidate.url not in visited:
                queue.append(candidate)

    raise RuntimeError(f"no PDF discovered for {year}-{month:02d} from {base_url}")

def try_common_pdf_urls(session, base_url, company_id, year, month, timeout):
    """Try common Indonesian financial report URL patterns."""
    month_label = MONTH_LABELS[month]
    parsed_base = urlparse(base_url)
    domain_base = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    patterns = [
        f"{domain_base}/assets/laporan-keuangan-{month_label.lower()}-{year}.pdf",
        f"{domain_base}/files/laporan-keuangan-{month_label.lower()}-{year}.pdf",
        f"{domain_base}/pdf/laporan-keuangan-{month_label.lower()}-{year}.pdf",
        f"{domain_base}/content/laporan-keuangan-{month_label.lower()}-{year}.pdf",
        f"{domain_base}/uploads/laporan-keuangan-{month_label.lower()}-{year}.pdf",
        f"{domain_base}/documents/laporan-keuangan-{month_label.lower()}-{year}.pdf",
        f"{domain_base}/financial-report/{year}/{month:02d}/laporan-keuangan.pdf",
        f"{domain_base}/laporan-keuangan-{month_label.lower()}-{year}.pdf",
    ]
    
    for url in patterns:
        try:
            response = session.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200 and 'pdf' in response.headers.get('content-type', '').lower():
                return PDFCandidate(url=url, text=f"Laporan Keuangan {month_label} {year}", 
                                   score=50, discovered_url=base_url)
        except Exception:
            pass
    return None


def validate_pdf(data):
    if len(data) < 16:
        return False
    if not data.startswith(b"%PDF-"):
        return False
    return b"%%EOF" in data[-2048:] if len(data) > 2048 else True

def fetch_html_static(session, url, timeout):
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text, url

def fetch_html_browser(url, timeout):
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")
    
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            _goto_with_fallback(page, url, timeout)
            _stabilize_browser_page(page, timeout)
            html = page.content()
            final_url = page.url
            return html, final_url
        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"browser timeout: {e}") from e
        except PlaywrightError as e:
            raise RuntimeError(f"browser error: {e}") from e
        finally:
            browser.close()

def fetch_html_browser_domready(url, timeout, extra_wait_ms=2500):
    """Fetch HTML using browser with domcontentloaded (faster than networkidle)."""
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(extra_wait_ms)
            html = page.content()
            final_url = page.url
            return html, final_url
        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"browser timeout: {e}") from e
        except PlaywrightError as e:
            raise RuntimeError(f"browser error: {e}") from e
        finally:
            browser.close()


def fetch_html_with_smart_fallback(session, url, year, month, timeout=30):
    """Fetch HTML with intelligent fallback to browser rendering.

    Tries static HTML first, then falls back to browser if:
    1. Static fetch fails with any error
    2. Static fetch succeeds but no PDFs are found (content is JS-rendered)
    """
    try:
        html, discovered_url = fetch_html_static(session, url, timeout)
        candidates = extract_pdf_links(html, discovered_url, year, month)
        if candidates:
            return html, discovered_url, False
        LOGGER.info("No PDFs found in static HTML, falling back to browser rendering")
    except Exception as e:
        LOGGER.info(f"Static fetch failed ({e}), falling back to browser rendering")
        html = ""
        discovered_url = url

    browser_attempts = (
        lambda: fetch_html_browser_report(url, timeout, year, month),
        lambda: fetch_html_browser_domready(url, timeout),
        lambda: fetch_html_browser(url, timeout),
    )
    last_error = None
    browser_html = html
    browser_url = discovered_url
    for fetcher in browser_attempts:
        try:
            fetched = fetcher()
            if len(fetched) == 3:
                candidate_html, candidate_url, pdf_hints = fetched
            else:
                candidate_html, candidate_url = fetched
                pdf_hints = []
            browser_html, browser_url = candidate_html, candidate_url
            if pdf_hints:
                candidate_html = _augment_html_with_pdf_hints(candidate_html, pdf_hints)
            candidates = extract_pdf_links(candidate_html, candidate_url, year, month)
            if candidates:
                return candidate_html, candidate_url, True
            if pdf_hints:
                return candidate_html, candidate_url, True
        except Exception as e:
            last_error = e
            LOGGER.info(f"Browser fetch failed ({e})")

    html, discovered_url = browser_html, browser_url

    try:
        candidate = discover_download_candidate(session, html, discovered_url, year, month, timeout=timeout, max_depth=3)
        if candidate and candidate.discovered_url:
            candidate_page_url = candidate.discovered_url
            LOGGER.info("Following report link page %s before PDF selection", candidate_page_url)
            try:
                report_html, report_url, pdf_hints = fetch_html_browser_report(candidate_page_url, timeout, year, month)
            except Exception:
                report_html, report_url = fetch_html_static(session, candidate_page_url, timeout)
                pdf_hints = []
            if pdf_hints:
                report_html = _augment_html_with_pdf_hints(report_html, pdf_hints)
            report_candidates = extract_pdf_links(report_html, report_url, year, month)
            if report_candidates:
                return report_html, report_url, True
            if pdf_hints:
                return report_html, report_url, True
    except Exception as e:
        last_error = e
        LOGGER.info(f"Recursive report discovery failed ({e})")

    if not html:
        raise RuntimeError(f"unable to discover report page: {last_error}")
    return html, discovered_url, True

def download_pdf(session, url, output_path, timeout=30, force=False):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_path.exists() and not force:
        existing = output_path.read_bytes()
        if validate_pdf(existing):
            return None, len(existing)
    
    with session.get(url, timeout=timeout, stream=True) as response:
        status = response.status_code
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, dir=str(output_path.parent), suffix=".part") as tmp:
            temp_path = Path(tmp.name)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            tmp.flush()
    
    data = temp_path.read_bytes()
    if not validate_pdf(data):
        temp_path.unlink()
        raise RuntimeError(f"Invalid PDF from {url}")
    
    temp_path.replace(output_path)
    return status, len(data)

def write_manifest(output_dir, rows):
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "download_manifest.csv"
    json_path = output_dir / "download_manifest.json"
    
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    
    LOGGER.info(f"wrote manifest: {csv_path}")

def write_debug_html(debug_dir, html, reason):
    debug_dir.mkdir(parents=True, exist_ok=True)
    if html:
        (debug_dir / "page.html").write_text(html, encoding="utf-8")
    (debug_dir / "reason.txt").write_text(reason + "\n", encoding="utf-8")
    LOGGER.info(f"wrote debug html: {debug_dir}")
