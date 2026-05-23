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
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError as RequestsSSLError
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
        or "/assets/pdf/" in path
        or "/pdf/" in path
        or "download=true" in query
        or "view=true" in query
    )

def current_timestamp():
    return datetime.now(MANIFEST_TIMEZONE).isoformat(timespec="seconds")

def build_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    # Enhanced retry strategy: include common HTTP errors and SSL issues
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        raise_on_status=False,  # Don't raise immediately, let us handle it
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    # Disable SSL warnings for cases where we need to verify=False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return session

def normalize_text(text):
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def month_terms(month):
    terms = list(MONTH_NAMES[month])
    terms.extend([f"{month:02d}", str(month)])
    return list(dict.fromkeys(terms))

def matches_target_period(text, year, month):
    """Enhanced period detection with multiple format support."""
    blob = normalize_text(text)
    if not blob:
        return False

    terms = month_terms(month)
    # Check for month match using multiple patterns
    month_hit = False
    for term in terms:
        # Skip single-digit month numbers to avoid false matches like "2" in "22"
        if term.isdigit() and len(term) == 1:
            # For single digits, require word boundary or specific patterns
            if re.search(rf'(?:^|\s|/|-){re.escape(term)}(?:\s|$|/|-|\.)', blob):
                month_hit = True
                break
        else:
            # For month names/full numbers, use standard word boundary
            if re.search(rf'(?<![a-z]){re.escape(term)}(?![a-z])', blob):
                month_hit = True
                break

    # Check for year match - must be exact year number, not part of another number
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
        blob_text = " ".join(part for part in [text, parent_text, grandparent_text] if part)
        url = urljoin(base_url, href)
        if not (href.lower().endswith(".pdf") or is_probable_pdf_url(url)):
            continue
        
        if matches_target_period(blob_text + " " + url, year, month):
            score = score_candidate(blob_text + " " + url, year, month)
            candidates.append(PDFCandidate(url=url, text=text, score=score, discovered_url=base_url))
    
    return sorted(candidates, key=lambda x: x.score, reverse=True)


def extract_report_links(html, base_url, year, month):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    keywords = ("laporan", "keuangan", "report", "unduh", "download", "cari laporan")
    for link in soup.find_all("a"):
        href = link.get("href", "").strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        text = link.get_text(" ", strip=True)
        parent_text = ""
        if link.parent:
            parent_text = link.parent.get_text(" ", strip=True)
        grandparent_text = ""
        if link.parent and link.parent.parent:
            grandparent_text = link.parent.parent.get_text(" ", strip=True)
        blob = " ".join(part for part in [text, parent_text, grandparent_text, href] if part)
        if not matches_target_period(blob, year, month):
            continue
        normalized = normalize_text(blob)
        if not any(keyword in normalized for keyword in keywords):
            continue
        url = urljoin(base_url, href)
        score = score_candidate(blob, year, month) + 5
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
                continue
            except Exception:
                pass

        if any(label in option_blob for label in ("konvensional", "syariah", "tahunan", "triwulan")):
            for label in ("Konvensional", "Syariah", "Tahunan"):
                try:
                    select.select_option(label=label)
                    break
                except Exception:
                    continue


def fetch_html_browser_report(url, timeout, year, month):
    if sync_playwright is None:
        raise RuntimeError("Playwright not installed; pip install playwright && playwright install chromium")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2200})
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            page.wait_for_timeout(750)
            _select_report_filters(page, year, month)
            try:
                page.get_by_role("button", name=re.compile(r"cari laporan", re.I)).first.click()
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                page.wait_for_timeout(750)
            except Exception:
                pass
            html = page.content()
            final_url = page.url
            return html, final_url
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
            response_html, current_base = fetch_html_static(session, current.url, timeout)
            current_html = response_html

        direct_candidates = extract_pdf_links(current_html, current_base, year, month)
        if direct_candidates:
            return direct_candidates[0]

        follow_candidates = extract_report_links(current_html, current_base, year, month)
        for candidate in follow_candidates:
            if candidate.url not in visited:
                queue.append(candidate)

    raise RuntimeError(f"no PDF discovered for {year}-{month:02d} from {base_url}")

def validate_pdf(data):
    if len(data) < 16:
        return False
    if not data.startswith(b"%PDF-"):
        return False
    return b"%%EOF" in data[-2048:] if len(data) > 2048 else True

def validate_document(data):
    """Validate PDF, JPEG, PNG, and other document formats."""
    if len(data) < 4:
        return False
    # PDF: starts with %PDF-
    if data.startswith(b"%PDF-"):
        return b"%%EOF" in data[-2048:] if len(data) > 2048 else True
    # JPEG: starts with FFD8FF
    if data.startswith(b"\xFF\xD8\xFF"):
        return True
    # PNG: starts with 89504E47
    if data.startswith(b"\x89PNG"):
        return True
    return False

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
            # Use domcontentloaded first (faster, less timeout-prone)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(500)
            html = page.content()
            final_url = page.url
            return html, final_url
        except (PlaywrightTimeoutError, PlaywrightError):
            # If domcontentloaded fails, try networkidle with longer timeout
            try:
                page.goto(url, wait_until="networkidle", timeout=(timeout * 2) * 1000)
                page.wait_for_timeout(500)
                html = page.content()
                final_url = page.url
                return html, final_url
            except PlaywrightTimeoutError as e:
                raise RuntimeError(f"browser timeout after retries: {e}") from e
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

    # Try with domcontentloaded first (faster, less timeout-prone)
    try:
        html, discovered_url = fetch_html_browser_domready(url, timeout)
        return html, discovered_url, True
    except Exception as e:
        LOGGER.info(f"Browser domcontentloaded failed ({e}), retrying with longer wait...")
        # Fall back to networkidle with longer timeout
        html, discovered_url = fetch_html_browser(url, timeout)
        return html, discovered_url, True

def download_pdf(session, url, output_path, timeout=30, force=False):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not force:
        existing = output_path.read_bytes()
        if validate_document(existing):
            return None, len(existing)

    def _download_stream(verify=True, headers=None):
        request_headers = headers or {}
        with session.get(url, timeout=timeout, stream=True, verify=verify, headers=request_headers) as response:
            status_code = response.status_code
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(output_path.parent), suffix=".part") as tmp:
                temp_file = Path(tmp.name)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
                tmp.flush()
        return status_code, temp_file

    try:
        status, temp_path = _download_stream(verify=True)
    except (RequestsSSLError, Exception) as e:
        message = str(e)
        # Retry with verify=False for SSL/HTTPS certificate errors
        if any(x in message for x in ["CERTIFICATE_VERIFY_FAILED", "SSLCertVerificationError", "SSLError"]):
            LOGGER.warning(
                "SSL certificate verification failed for %s; retrying with verify=False",
                url,
            )
            try:
                status, temp_path = _download_stream(verify=False)
            except Exception as e2:
                LOGGER.error("SSL fallback also failed: %s", e2)
                raise
        # Retry with Referer and then non-browser UA for 403 Forbidden
        elif "403" in message or "Forbidden" in message:
            LOGGER.warning("Got 403 Forbidden; retrying with Referer header and modified User-Agent")
            domain = url.split('/')[2] if '//' in url else ''
            referer = f"https://{domain}/" if domain else "https://www.google.com/"
            try:
                status, temp_path = _download_stream(verify=True, headers={"Referer": referer})
            except Exception as e_referer:
                # Some servers block browser-like UA but allow simple clients
                if "403" not in str(e_referer) and "Forbidden" not in str(e_referer):
                    raise
                LOGGER.warning("Referer retry still returned 403; retrying with generic client UA")
                try:
                    status, temp_path = _download_stream(
                        verify=True,
                        headers={
                            "Referer": referer,
                            "User-Agent": "python-requests/2.31.0",
                            "Accept": "*/*",
                        },
                    )
                except Exception as e3:
                    LOGGER.error("All 403 retry attempts failed: %s", e3)
                    raise
        # Retry with timeout increase for connection/read timeouts
        elif any(x in message for x in ["timeout", "timed out", "Read timed out", "ConnectTimeout"]):
            LOGGER.warning("Timeout during download; retrying with increased timeout")
            try:
                # Increase timeout and retry
                new_timeout = max(timeout * 2, 120)
                status, temp_path = _download_stream(verify=True)
            except Exception as e_timeout:
                LOGGER.error("Timeout retry also failed: %s", e_timeout)
                raise
        else:
            LOGGER.error("Download failed with error: %s", message)
            raise
    
    data = temp_path.read_bytes()
    if not validate_document(data):
        temp_path.unlink()
        raise RuntimeError(f"Invalid document from {url}")
    
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
