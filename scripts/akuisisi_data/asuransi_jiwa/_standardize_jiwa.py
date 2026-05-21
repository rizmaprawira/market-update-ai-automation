#!/usr/bin/env python3
"""Batch standardization script for asuransi_jiwa download scripts."""

import re
import sys
from pathlib import Path

def standardize_script(script_path):
    """Apply standardization fixes to a single script."""
    with open(script_path, "r") as f:
        content = f.read()
    
    original = content
    
    # 1. Add bootstrap path if missing
    if 'sys.path.insert' not in content:
        import_section = content.find('from _downloader_base')
        if import_section > 0:
            insert_pos = content.rfind('\n', 0, import_section)
            content = content[:insert_pos] + '\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))' + content[insert_pos:]
    
    # 2. Fix output path: remove "raw_pdf" folder
    content = re.sub(
        r'output_dir = .*?/ "raw_pdf" / CATEGORY / COMPANY_ID',
        'output_dir = args.output_root / period / CATEGORY / COMPANY_ID',
        content
    )
    
    # 3. Fix filename format from {period} string to YYYY_MM
    content = re.sub(
        r'output_pdf = output_dir / f"{COMPANY_ID}_{period}\.pdf"',
        'output_pdf = output_dir / f"{COMPANY_ID}_{args.year:04d}_{args.month:02d}.pdf"',
        content
    )
    
    # 4. Add --yyyy and --mm aliases if missing
    if '--yyyy' not in content:
        # Find --year argument and add --yyyy alias
        content = re.sub(
            r'(parser\.add_argument\("--year".*?dest="year")',
            r'\1, "-y"',
            content,
            flags=re.DOTALL
        )
        # Add --yyyy alias after --year
        content = re.sub(
            r'(parser\.add_argument\("--year"[^)]+\))',
            r'\1\n    parser.add_argument("--yyyy", dest="year", type=int, help="Target year (alias for --year)")',
            content,
            flags=re.DOTALL
        )
    
    if '--mm' not in content:
        # Add --mm alias after --month
        content = re.sub(
            r'(parser\.add_argument\("--month"[^)]+\))',
            r'\1\n    parser.add_argument("--mm", dest="month", type=int, help="Target month 1-12 (alias for --month)")',
            content,
            flags=re.DOTALL
        )
    
    # 5. Add --discover-only flag if missing
    if '--discover-only' not in content:
        content = re.sub(
            r'(parser\.add_argument\("--dry-run"[^)]+\))',
            r'\1\n    parser.add_argument("--discover-only", action="store_true", help="Stop after discovery, return 0")',
            content,
            flags=re.DOTALL
        )
    
    if original != content:
        with open(script_path, "w") as f:
            f.write(content)
        return True
    return False

# Find all asuransi_jiwa scripts
scripts_dir = Path("/Users/rizzie/Work/IndonesiaRe/market-update-automation-codex/scripts/akuisisi_data/asuransi_jiwa")
scripts = sorted(scripts_dir.glob("pt_*/pt_*_download.py"))

print(f"Found {len(scripts)} scripts to standardize")

changed = 0
for script in scripts:
    if standardize_script(script):
        changed += 1
        print(f"✓ {script.parent.name}")
    else:
        print(f"- {script.parent.name} (no changes)")

print(f"\nChanged {changed}/{len(scripts)} scripts")
