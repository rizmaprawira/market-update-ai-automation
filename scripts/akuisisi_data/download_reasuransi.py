"""Orchestrate downloads for all reinsurance companies."""
from __future__ import annotations

import argparse
import csv
import logging
import subprocess
import sys
import time
import webbrowser
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

LOGGER = logging.getLogger("download_reasuransi")
SCRIPT_DIR = Path(__file__).parent
CATEGORY = "reasuransi"

# Company ID to source website URL mapping for fallback investigation
COMPANY_WEBSITES = {
    "indonesiare": "https://www.indonesiare.co.id/id/investor-relations/financial-report",
    "indore": "https://www.indonesiare.co.id/id/investor-relations/financial-report",
    "inare": "https://inare.co.id/en/report/",
    "maipark": "https://maipark.com/id/corporate/laporan",
    "nasre": "https://nasionalre.id/laporan-tahunan",
    "marein": "https://marein-re.com/laporan-keuangan",
    "orionre": "https://www.orionre.id/id/publikasi.html",
    "tugure": "https://www.tugure.id/id/financial/monthly",
    "nusantarare": "https://nusantarare.com/report/?lang=in",
}


def get_all_company_scripts() -> list[Path]:
    """Return sorted list of all company download scripts."""
    scripts = sorted(SCRIPT_DIR.glob("reasuransi/**/*_download.py"))
    return [
        script
        for script in scripts
        if script.is_file()
    ]


def open_website_for_investigation(company_id: str) -> None:
    """Open company website for manual investigation on download failure."""
    url = COMPANY_WEBSITES.get(company_id)
    if url:
        try:
            webbrowser.open(url)
            LOGGER.info(f"Opened {company_id} website for investigation: {url}")
        except Exception as e:
            LOGGER.warning(f"Failed to open browser for {company_id}: {e}")
    else:
        LOGGER.warning(f"No website URL configured for {company_id}")


def run_single_company(
    script_path: Path,
    year: int,
    month: int,
    *,
    dry_run: bool = False,
    discover_only: bool = False,
    timeout: int = 30,
    use_browser: bool = False,
    force: bool = False,
    debug_html: bool = False,
    output_root: Path = Path("data"),
    process_timeout: int | None = None,
) -> dict[str, object]:
    """Run one company script and classify the result."""
    company_id = script_path.stem.replace("_download", "")

    cmd = [
        sys.executable,
        str(script_path),
        "--year",
        str(year),
        "--month",
        str(month),
        "--timeout",
        str(timeout),
        "--output-root",
        str(output_root),
    ]

    if dry_run:
        cmd.append("--dry-run")
    if discover_only:
        cmd.append("--discover-only")
    if force:
        cmd.append("--force")
    if debug_html:
        cmd.append("--debug-html")
    if use_browser:
        cmd.append("--use-browser")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=process_timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "company_id": company_id,
            "status": "timeout",
            "reason": "Script timeout",
            "returncode": 124,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "company_id": company_id,
            "status": "error",
            "reason": f"Exception: {str(exc)[:80]}",
            "returncode": -1,
        }

    output = f"{result.stdout}\n{result.stderr}".strip()
    lower_output = output.lower()

    if result.returncode == 0:
        if (
            "status=downloaded" in lower_output
            or "downloaded conventional financial report pdf" in lower_output
        ):
            status = "success"
            reason = "Downloaded"
        elif (
            "status=skipped_existing" in lower_output
            or "existing valid pdf was kept" in lower_output
        ):
            status = "already_exists"
            reason = "Already downloaded"
        elif "status=discover_only" in lower_output or "discover-only mode" in lower_output:
            status = "discover_only"
            reason = "Discovery only"
        elif "dry-run requested" in lower_output or "status=dry_run" in lower_output:
            status = "dry_run"
            reason = "Dry-run completed"
        else:
            status = "success"
            reason = "Completed"
    else:
        if (
            "no matching reports found" in lower_output
            or "no pdf links were found" in lower_output
            or "no conventional monthly financial report pdf" in lower_output
        ):
            status = "no_pdf"
            reason = "No PDF found"
        elif (
            "403" in output
            or "forbidden" in lower_output
            or "429" in output
            or "rate limit" in lower_output
        ):
            status = "rate_limited"
            reason = "Rate limited"
        elif "browser timeout" in lower_output or "request timeout" in lower_output:
            status = "timeout"
            reason = "Connection timeout"
        else:
            status = "error"
            reason = f"Error (exit code {result.returncode})"

    return {
        "company_id": company_id,
        "status": status,
        "reason": reason,
        "returncode": result.returncode,
        "output_snippet": output.splitlines()[-3:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download financial reports for all reinsurance companies",
    )
    parser.add_argument("--year", type=int, required=True, help="Target year")
    parser.add_argument("--month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no download")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDFs")
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failures")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per script in seconds")
    parser.add_argument(
        "--process-timeout",
        type=int,
        default=0,
        help="Wall-clock timeout for each child process in seconds; 0 disables it.",
    )
    parser.add_argument("--use-browser", action="store_true", help="Use browser rendering")
    parser.add_argument(
        "--no-fallback-browser",
        action="store_true",
        help="Disable automatic browser opening on download failures",
    )
    parser.add_argument("--output-root", type=Path, default=Path("data"))
    args = parser.parse_args()

    if not 1 <= args.month <= 12:
        print("Error: Month must be 1-12")
        return 1

    if args.parallel < 1:
        print("Error: Parallel workers must be >= 1")
        return 1

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    period = f"{args.year:04d}-{args.month:02d}"
    scripts = get_all_company_scripts()

    if not scripts:
        print("Error: No company download scripts found")
        return 1

    process_timeout = None if args.process_timeout <= 0 else args.process_timeout

    print("\n" + "=" * 80)
    print(f"REINSURANCE BATCH DOWNLOADER - {period}")
    print("=" * 80)
    print(f"Total companies: {len(scripts)}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'DOWNLOAD'}")
    if args.discover_only:
        print("Discover only: ENABLED")
    if args.force:
        print("Force overwrite: ENABLED")
    if args.debug_html:
        print("Debug HTML: ENABLED")
    print(f"Parallel workers: {args.parallel}")
    print(f"Timeout per script: {args.timeout}s")
    if args.use_browser:
        print("Browser rendering: ENABLED")
    if not args.no_fallback_browser:
        print("Fallback browser: ENABLED (opens on errors)")
    print("=" * 80 + "\n")

    results: list[dict[str, object]] = []
    start_time = time.time()

    if args.parallel == 1:
        for idx, script in enumerate(scripts, 1):
            company_id = script.stem.replace("_download", "")
            print(f"[{idx:2d}/{len(scripts)}] {company_id}...", end=" ", flush=True)

            result = run_single_company(
                script,
                args.year,
                args.month,
                dry_run=args.dry_run,
                discover_only=args.discover_only,
                timeout=args.timeout,
                use_browser=args.use_browser,
                force=args.force,
                debug_html=args.debug_html,
                output_root=args.output_root,
                process_timeout=process_timeout,
            )
            results.append(result)

            status = result["status"]
            reason = result["reason"]
            if status == "success":
                print(f"✅ {reason}")
            elif status in {"dry_run", "discover_only"}:
                print(f"✓ {reason}")
            elif status == "no_pdf":
                print(f"❌ {reason}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
            elif status == "rate_limited":
                print(f"⚠️  {reason}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
            elif status == "timeout":
                print(f"⏱️  {reason}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
            elif status == "already_exists":
                print(f"📦 {reason}")
            else:
                print(f"❓ {reason}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
    else:
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {
                executor.submit(
                    run_single_company,
                    script,
                    args.year,
                    args.month,
                    dry_run=args.dry_run,
                    discover_only=args.discover_only,
                    timeout=args.timeout,
                    use_browser=args.use_browser,
                    force=args.force,
                    debug_html=args.debug_html,
                    output_root=args.output_root,
                    process_timeout=process_timeout,
                ): script
                for script in scripts
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                results.append(result)

                status = result["status"]
                status_icon = {
                    "success": "✅",
                    "dry_run": "✓",
                    "discover_only": "✓",
                    "no_pdf": "❌",
                    "rate_limited": "⚠️ ",
                    "timeout": "⏱️ ",
                    "already_exists": "📦",
                    "error": "❓",
                }.get(str(status), "?")

                print(
                    f"[{completed:2d}/{len(scripts)}] {status_icon} "
                    f"{result['company_id']}: {result['reason']}"
                )

                # Open website for investigation on failure
                if (
                    not args.no_fallback_browser
                    and status in {"error", "no_pdf", "rate_limited", "timeout"}
                ):
                    open_website_for_investigation(result["company_id"])

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    summary = defaultdict(int)
    for result in results:
        summary[str(result["status"])] += 1

    status_labels = {
        "success": "✅ Downloaded",
        "dry_run": "✓ Found (dry-run)",
        "discover_only": "✓ Discovery only",
        "already_exists": "📦 Already exists",
        "no_pdf": "❌ No PDF found",
        "rate_limited": "⚠️  Rate limited",
        "timeout": "⏱️  Timeout",
        "error": "❓ Error",
    }

    for status, label in status_labels.items():
        count = summary[status]
        if count > 0:
            pct = (count / len(results)) * 100
            print(f"{label:25s}: {count:3d} ({pct:5.1f}%)")

    print(f"\nTotal time: {elapsed:.1f}s ({elapsed / len(results):.1f}s per company)")
    print("=" * 80)

    report_path = args.output_root / period / "raw_pdf" / CATEGORY / "batch_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["company_id", "status", "reason", "returncode"])
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "company_id": result["company_id"],
                    "status": result["status"],
                    "reason": result["reason"],
                    "returncode": result["returncode"],
                }
            )

    print(f"\nDetailed report saved to: {report_path}")

    print("\nBreakdown:")
    print(
        f"  Working companies:  "
        f"{summary['success'] + summary['dry_run'] + summary['discover_only']}"
    )
    print(f"  No public PDFs:     {summary['no_pdf']}")
    print(f"  Rate limited:       {summary['rate_limited']}")
    print(f"  Timeouts:           {summary['timeout']}")
    print(f"  Errors:             {summary['error']}")

    total_success = (
        summary["success"]
        + summary["dry_run"]
        + summary["discover_only"]
        + summary["already_exists"]
    )
    if total_success == len(results):
        print(f"\n✅ All {len(results)} companies processed successfully!")
        return 0
    if total_success >= len(results) * 0.7:
        print(f"\n✓ {total_success}/{len(results)} companies successful")
        return 0

    print(f"\n⚠️  Only {total_success}/{len(results)} companies successful")
    return 1


if __name__ == "__main__":
    sys.exit(main())
