"""Orchestrate downloads for all 48 life insurance companies."""
import argparse
import csv
import logging
import subprocess
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from collections import defaultdict

LOGGER = logging.getLogger("download_asuransi_jiwa")
SCRIPT_DIR = Path(__file__).parent
CATEGORY = "asuransi_jiwa"

# Company ID to source website URL mapping (sourced from assets/link_asuransi_jiwa.xlsx)
COMPANY_WEBSITES = {
    "pt_aia_financial": "https://www.aia-financial.co.id/id/about-aia/laporan-penting/report-financial",
    "pt_ajb_bumiputera_1912": "https://www.bumiputera.com/listdocument/document/our_company/financial_report/0/15/0/1",
    "pt_asuransi_allianz_life_indonesia": "https://www.allianz.co.id/tentang-kami/finansial.html",
    "pt_asuransi_bri_life": "https://brilife.co.id/laporan-keuangan",
    "pt_asuransi_ciputra_indonesia": "https://www.ciputralife.com/index.php/tentang-kami/laporan-keuangan",
    "pt_asuransi_jiwa_astra": "https://www.astralife.co.id/laporan-keuangan/",
    "pt_asuransi_jiwa_bca": "https://www.bcalife.co.id/tentang-kami/laporan-keuangan",
    "pt_asuransi_jiwa_central_asia_raya": "https://www.car.co.id/tentang-kami/informasi-umum/laporan-keuangan/",
    "pt_asuransi_jiwa_generali_indonesia": "https://www.generali.co.id/id/laporan-keuangan",
    "pt_asuransi_jiwa_ifg": "https://ifg-life.id/about?propKey=report&subValue=&optional=",
    "pt_asuransi_jiwa_mandiri_inhealth_indonesia": "https://www.inhealth.co.id/id/gcg",
    "pt_asuransi_jiwa_manulife_indonesia": "https://www.manulife.co.id/id/tentang-kami/laporan-keuangan.html",
    "pt_asuransi_jiwa_nasional": "https://www.nasionallife.co.id/Financial_Reports.html",
    "pt_asuransi_jiwa_reliance_indonesia": "https://reliance-life.co.id/keuangan",
    "pt_asuransi_jiwa_sealnsure": "https://moneeinsure.co.id/about-us/life/statement",
    "pt_asuransi_jiwa_sequis_financial": "https://www.sequis.co.id/id/tentang-sequis/financial/laporan-perusahaan",
    "pt_asuransi_jiwa_sequis_life": "https://www.sequis.co.id/id/tentang-sequis/life/laporan-perusahaan",
    "pt_asuransi_jiwa_starinvestama": "https://www.starinvestama.co.id/laporan_keuangan.html",
    "pt_asuransi_jiwa_taspen": "https://www.taspenlife.com/about?tab=laporan",
    "pt_asuransi_jiwa_teguh_pelita_pelindung": "https://equiralife.co.id/id/report/financial",
    "pt_asuransi_simas_jiwa": "https://about.simasjiwa.co.id/kinerja",
    "pt_avrist_assurance": "https://www.avrist.com/tentang-avrist-life/tentang-avrist-life?tab=Laporan+Perusahaan",
    "pt_axa_financial_indonesia": "https://www.axa.co.id/laporan-tahunan-afi",
    "pt_axa_mandiri_financial_services": "https://www.axa-mandiri.co.id/laporan-keuangan-detail",
    "pt_bhinneka_life_indonesia": "https://www.bhinnekalife.com/id/laporan-keuangan",
    "pt_bni_life_insurance": "https://www.bni-life.co.id/id/laporan_perusahaan",
    "pt_capital_life_indonesia": "https://www.capitallife.co.id/laporan",
    "pt_central_asia_financial__jagadiri_": "https://jagadiri.co.id/laporan-keuangan",
    "pt_china_life_insurance_indonesia": "https://www.chinalife.co.id/id/public-disclosure",
    "pt_chubb_life_insurance": "https://www.chubb.com/id-id/about-chubb/pt-chubb-life-insurance-indonesia-financial-report.html",
    "pt_equity_life_indonesia": "https://www.equity.co.id/about/report",
    "pt_fwd_insurance_indonesia": "https://www.fwd.co.id/id/tentang-kami/",
    "pt_great_eastern_life_indonesia": "https://www.greateasternlife.com/id/in/tentang-kami/pusat-media/laporan-tahunan.html",
    "pt_hanwha_life_insurance_indonesia": "https://www.hanwhalife.co.id/laporan-keuangan/",
    "pt_heksa_solution_insurance": "https://www.heksainsurance.co.id/about/companyreport",
    "pt_indolife_pensiontama": "https://indolife.co.id/Read/Detail/laporan--perusahaan",
    "pt_lippo_life_assurance": "https://lippolife.co.id/company/non-audited/monthly-report",
    "pt_mnc_life_assurance": "https://www.mnclife.com/about/laporanKeuangan",
    "pt_msig_life_insurance_indonesia_tbk": "https://www.msiglife.co.id/tentang-kami/laporan-keuangan",
    "pt_pacific_life_insurance": "https://www.pacificlife.co.id/laporan-keuangan",
    "pt_panin_dai-chi_life": "https://www.panindai-ichilife.co.id/id/laporan-keuangan",
    "pt_perta_life_insurance": "https://pertalife.com/web/laporan-keuangan-1",
    "pt_pfi_mega_life_insurance": "https://pfimegalife.co.id/tentang-kami/laporan-keuangan",
    "pt_prudential_life_assurance": "https://www.prudential.co.id/id/about-prudential-indonesia/financial-statement/",
    "pt_sun_life_financial_indonesia": "https://www.sunlife.co.id/id/about-us/who-we-are/financial-report/",
    "pt_tokio_marine_life_insurance_indonesia": "https://www.tokiomarine.com/id/id/life/about-us/financial-information.html",
    "pt_victoria_alife_indonesia": "https://www.victorialife.co.id/layanan-kami/",
    "pt_zurich_topas_life": "https://www.zurich.co.id/en/tentang-kami/zurich-topas-life/informasi-investor",
}


def get_all_company_scripts():
    """Return sorted list of all download_pt_*.py scripts."""
    scripts = sorted(SCRIPT_DIR.glob("download_pt_*.py"))
    return [s for s in scripts if s.is_file()]


def check_if_pdf_exists(company_id, year, month, output_root):
    """Check if PDF already exists for a company."""
    period = f"{year:04d}-{month:02d}"
    output_dir = output_root / period / "raw_pdf" / CATEGORY / company_id
    output_pdf = output_dir / f"{company_id}_{period}.pdf"
    return output_pdf.exists() and output_pdf.stat().st_size > 0


def open_website_for_investigation(company_id):
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
    script_path,
    year,
    month,
    *,
    dry_run=False,
    discover_only=False,
    timeout=30,
    use_browser=False,
    force=False,
    debug_html=False,
    output_root=Path("data"),
    process_timeout=None,
):
    """Run a single company's download script and return results."""
    company_id = script_path.stem.replace("download_", "")

    # Check if PDF already exists (unless dry-run)
    if not dry_run and output_root and check_if_pdf_exists(company_id, year, month, output_root):
        return {
            "company_id": company_id,
            "status": "already_exists",
            "reason": "PDF already downloaded",
            "returncode": 0,
            "output_snippet": []
        }

    cmd = [
        sys.executable, str(script_path),
        "--year", str(year),
        "--month", str(month),
        "--timeout", str(timeout),
        "--output-root", str(output_root),
    ]

    if dry_run or discover_only:
        cmd.append("--dry-run")
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
            timeout=process_timeout
        )

        output = result.stdout + result.stderr
        lower_output = output.lower()

        # Determine status from output
        if "Successfully downloaded" in output:
            status = "success"
            reason = "Downloaded"
        elif discover_only and result.returncode == 0:
            status = "discover_only"
            reason = "Discovery only"
        elif "Dry-run complete" in output or "Dry-run:" in output:
            status = "dry_run"
            reason = "Dry-run (PDF found)"
        elif "no PDF candidates found" in output or "no pdf candidates found" in lower_output:
            status = "no_pdf"
            reason = "No PDF found"
        elif "403" in output or "Forbidden" in output or "429" in output or "rate limit" in lower_output:
            status = "rate_limited"
            reason = "Rate limited"
        elif "already exists" in output or "already_exists" in output:
            status = "already_exists"
            reason = "Already downloaded"
        elif "timeout" in output.lower() or result.returncode == 124:
            status = "timeout"
            reason = "Connection timeout"
        elif result.returncode != 0:
            status = "error"
            reason = f"Error (exit code {result.returncode})"
        else:
            status = "success"
            reason = "Completed"

        return {
            "company_id": company_id,
            "status": status,
            "reason": reason,
            "returncode": result.returncode,
            "output_snippet": output.split('\n')[-3:-1]
        }

    except subprocess.TimeoutExpired:
        return {
            "company_id": company_id,
            "status": "timeout",
            "reason": "Script timeout",
            "returncode": 124,
            "output_snippet": []
        }
    except Exception as e:
        return {
            "company_id": company_id,
            "status": "error",
            "reason": f"Exception: {str(e)[:50]}",
            "returncode": -1,
            "output_snippet": []
        }


def main():
    parser = argparse.ArgumentParser(
        description="Download financial reports for all 48 life insurance companies"
    )
    parser.add_argument("--year", type=int, required=True, help="Target year")
    parser.add_argument("--month", type=int, required=True, help="Target month (1-12)")
    parser.add_argument("--dry-run", action="store_true", help="Discovery only, no download")
    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDFs")
    parser.add_argument("--debug-html", action="store_true", help="Save debug HTML on failures")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel workers (default: 1)")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per script in seconds")
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
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    period = f"{args.year:04d}-{args.month:02d}"
    scripts = get_all_company_scripts()

    if not scripts:
        print("Error: No company download scripts found")
        return 1

    process_timeout = None if args.process_timeout <= 0 else args.process_timeout

    print("\n" + "="*80)
    print(f"ASURANSI JIWA BATCH DOWNLOADER - {period}")
    print("="*80)
    print(f"Total companies: {len(scripts)}")
    mode = "DISCOVER-ONLY" if args.discover_only else ("DRY-RUN" if args.dry_run else "DOWNLOAD")
    print(f"Mode: {mode}")
    if args.discover_only:
        print("Discover only: ENABLED")
    if args.force:
        print("Force overwrite: ENABLED")
    if args.debug_html:
        print("Debug HTML: ENABLED")
    print(f"Parallel workers: {args.parallel}")
    print(f"Timeout per script: {args.timeout}s")
    if args.use_browser:
        print(f"Browser rendering: ENABLED")
    if not args.no_fallback_browser:
        print("Fallback browser: ENABLED (opens on errors)")
    print("="*80 + "\n")

    # Run downloads
    results = []
    start_time = time.time()

    if args.parallel == 1:
        # Sequential execution
        for idx, script in enumerate(scripts, 1):
            company_id = script.stem.replace("download_", "")
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
            # Status indicator
            if status == "success":
                print(f"✅ {result['reason']}")
            elif status == "dry_run":
                print(f"✓ {result['reason']}")
            elif status == "discover_only":
                print(f"✓ {result['reason']}")
            elif status == "no_pdf":
                print(f"❌ {result['reason']}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
            elif status == "rate_limited":
                print(f"⚠️  {result['reason']}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
            elif status == "timeout":
                print(f"⏱️  {result['reason']}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
            elif status == "already_exists":
                print(f"📦 {result['reason']}")
            else:
                print(f"❓ {result['reason']}")
                if not args.no_fallback_browser:
                    open_website_for_investigation(company_id)
    else:
        # Parallel execution
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
                ): script for script in scripts
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                results.append(result)

                company_id = result["company_id"]
                status = result["status"]
                status_icon = {
                    "success": "✅",
                    "dry_run": "✓",
                    "discover_only": "✓",
                    "no_pdf": "❌",
                    "rate_limited": "⚠️ ",
                    "timeout": "⏱️ ",
                    "already_exists": "📦",
                    "error": "❓"
                }.get(status, "?")

                print(f"[{completed:2d}/{len(scripts)}] {status_icon} {company_id}: {result['reason']}")

                # Open website for investigation on failure
                if (
                    not args.no_fallback_browser
                    and status in {"error", "no_pdf", "rate_limited", "timeout"}
                ):
                    open_website_for_investigation(company_id)

    elapsed = time.time() - start_time

    # Aggregate results
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    summary = defaultdict(int)
    for result in results:
        summary[result["status"]] += 1

    status_labels = {
        "success": "✅ Downloaded",
        "dry_run": "✓ Found (dry-run)",
        "discover_only": "✓ Discovery only",
        "no_pdf": "❌ No PDF found",
        "rate_limited": "⚠️  Rate limited",
        "timeout": "⏱️  Timeout",
        "already_exists": "📦 Already exists",
        "error": "❓ Error"
    }

    for status, label in status_labels.items():
        count = summary[status]
        if count > 0:
            pct = (count / len(results)) * 100
            print(f"{label:25s}: {count:3d} ({pct:5.1f}%)")

    print(f"\nTotal time: {elapsed:.1f}s ({elapsed/len(results):.1f}s per company)")
    print("="*80)

    # Save detailed report
    report_path = args.output_root / period / "raw_pdf" / CATEGORY / "batch_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["company_id", "status", "reason", "returncode"])
        writer.writeheader()
        for result in results:
            writer.writerow({
                "company_id": result["company_id"],
                "status": result["status"],
                "reason": result["reason"],
                "returncode": result["returncode"]
            })

    print(f"\nDetailed report saved to: {report_path}")

    # Summary by status
    print(f"\nBreakdown:")
    print(f"  Working companies:  {summary['success'] + summary['dry_run'] + summary['discover_only']}")
    print(f"  No public PDFs:     {summary['no_pdf']}")
    print(f"  Rate limited:       {summary['rate_limited']}")
    print(f"  Timeouts:           {summary['timeout']}")
    print(f"  Errors:             {summary['error'] + summary.get('unknown', 0)}")

    # Determine exit code
    total_success = summary['success'] + summary['dry_run'] + summary['discover_only'] + summary['already_exists']
    if total_success == len(results):
        print(f"\n✅ All {len(results)} companies processed successfully!")
        return 0
    elif total_success >= len(results) * 0.7:
        print(f"\n✓ {total_success}/{len(results)} companies successful")
        return 0
    else:
        print(f"\n⚠️  Only {total_success}/{len(results)} companies successful")
        return 1


if __name__ == "__main__":
    sys.exit(main())
