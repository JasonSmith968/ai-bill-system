#!/usr/bin/env python3
"""
Dependency Security Audit Script
=================================
Checks for known vulnerabilities and dependency issues.

Usage:
    python scripts/dependency_audit.py
    python scripts/dependency_audit.py --json
    python scripts/dependency_audit.py --fix

Requirements:
    pip install pip-audit (optional, for CVE checking)
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
REQUIREMENTS_LOCK = PROJECT_ROOT / "backend" / "requirements-lock.txt"
REQUIREMENTS_IN = PROJECT_ROOT / "backend" / "requirements.in"
REPORT_FILE = PROJECT_ROOT / "dependency_audit_report.json"


# ============================================================================
# Requirement Parser
# ============================================================================

def parse_lock_file(filepath: Path) -> List[Dict]:
    """Parse requirements-lock.txt and extract package info."""
    packages = []

    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return packages

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Handle line continuations
            while line.endswith('\\'):
                line = line[:-1].strip()

            # Skip hash lines
            if line.startswith('--hash='):
                continue

            # Parse package==version
            match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[([^\]]+)\])?==(.+)$', line)
            if match:
                name = match.group(1)
                extras = match.group(2) or ""
                version = match.group(3).strip()

                packages.append({
                    "name": name,
                    "extras": extras,
                    "version": version,
                    "line": line_num,
                })

    return packages


def parse_in_file(filepath: Path) -> List[Dict]:
    """Parse requirements.in and extract abstract requirements."""
    requirements = []

    if not filepath.exists():
        return requirements

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            # Parse package>=version or package==version
            match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[([^\]]+)\])?\s*(>=|==|<=|~=)?\s*(.+)?$', line)
            if match:
                requirements.append({
                    "name": match.group(1),
                    "extras": match.group(2) or "",
                    "operator": match.group(3) or ">=",
                    "version": match.group(4) or "",
                })

    return requirements


# ============================================================================
# Security Checks
# ============================================================================

def check_pip_audit(packages: List[Dict]) -> List[Dict]:
    """Run pip-audit to check for known vulnerabilities."""
    vulns = []

    # Check if pip-audit is installed
    try:
        subprocess.run(
            ["pip-audit", "--version"],
            capture_output=True,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: pip-audit not installed. Install with: pip install pip-audit")
        return vulns

    # Run pip-audit
    try:
        # Create temporary requirements file
        temp_req = PROJECT_ROOT / ".tmp_audit_requirements.txt"
        with open(temp_req, 'w') as f:
            for pkg in packages:
                f.write(f"{pkg['name']}=={pkg['version']}\n")

        result = subprocess.run(
            ["pip-audit", "--requirement", str(temp_req), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.stdout:
            audit_data = json.loads(result.stdout)
            for item in audit_data:
                vulns.append({
                    "package": item.get("name"),
                    "version": item.get("version"),
                    "vuln_id": item.get("id"),
                    "description": item.get("description", ""),
                    "fix_version": item.get("fix_versions", [None])[0],
                    "aliases": item.get("aliases", []),
                })

        # Cleanup
        temp_req.unlink(missing_ok=True)

    except subprocess.TimeoutExpired:
        print("Warning: pip-audit timed out")
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse pip-audit output: {e}")
    except Exception as e:
        print(f"Warning: pip-audit failed: {e}")

    return vulns


def check_outdated(packages: List[Dict]) -> List[Dict]:
    """Check for outdated packages using pip."""
    outdated = []

    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0 and result.stdout:
            outdated_data = json.loads(result.stdout)

            # Create lookup of installed packages
            installed = {pkg["name"].lower(): pkg for pkg in packages}

            for item in outdated_data:
                name_lower = item["name"].lower()
                if name_lower in installed:
                    outdated.append({
                        "package": item["name"],
                        "installed": item["version"],
                        "latest": item["latest_version"],
                        "type": item.get("latest_filetype", "sdist"),
                    })

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not check outdated packages: {e}")

    return outdated


def check_duplicates(packages: List[Dict]) -> List[Dict]:
    """Check for duplicate packages with different versions."""
    seen = {}
    duplicates = []

    for pkg in packages:
        name_lower = pkg["name"].lower().replace("-", "_")
        if name_lower in seen:
            duplicates.append({
                "package": pkg["name"],
                "versions": [seen[name_lower]["version"], pkg["version"]],
                "lines": [seen[name_lower]["line"], pkg["line"]],
            })
        else:
            seen[name_lower] = pkg

    return duplicates


def check_conflicts(packages: List[Dict]) -> Tuple[bool, str]:
    """Run pip check for dependency conflicts."""
    try:
        result = subprocess.run(
            ["pip", "check"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def verify_hashes(filepath: Path) -> Tuple[bool, List[str]]:
    """Verify hash entries in lock file."""
    issues = []

    if not filepath.exists():
        return False, ["Lock file not found"]

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Count hash entries
    hash_count = content.count("--hash=sha256:")
    package_count = len(re.findall(r'^[a-zA-Z][a-zA-Z0-9_-]*==', content, re.MULTILINE))

    if hash_count == 0:
        issues.append("No hash entries found - run lock_dependencies.py --with-hashes")

    # Check for placeholder hashes
    if "PLACEHOLDER_HASH" in content:
        issues.append("Placeholder hashes found - need to generate real hashes")

    return len(issues) == 0, issues


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(
    packages: List[Dict],
    abstract_reqs: List[Dict],
    vulns: List[Dict],
    outdated: List[Dict],
    duplicates: List[Dict],
    conflicts_ok: bool,
    conflicts_msg: str,
    hashes_ok: bool,
    hash_issues: List[str]
) -> Dict:
    """Generate comprehensive audit report."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "project": "AI Accounting System",
        "python_version": sys.version.split()[0],
        "summary": {
            "total_packages": len(packages),
            "abstract_requirements": len(abstract_reqs),
            "vulnerability_count": len(vulns),
            "outdated_count": len(outdated),
            "duplicate_count": len(duplicates),
            "has_conflicts": not conflicts_ok,
            "hashes_verified": hashes_ok,
        },
        "packages": packages,
        "vulnerabilities": vulns,
        "outdated": outdated,
        "duplicates": duplicates,
        "conflicts": {
            "ok": conflicts_ok,
            "message": conflicts_msg,
        },
        "hash_verification": {
            "verified": hashes_ok,
            "issues": hash_issues,
        },
        "recommendations": [],
    }

    # Generate recommendations
    if vulns:
        report["recommendations"].append({
            "priority": "critical",
            "message": f"Address {len(vulns)} known vulnerabilities",
            "action": "Run: pip-audit --fix",
        })

    if duplicates:
        report["recommendations"].append({
            "priority": "high",
            "message": f"Remove {len(duplicates)} duplicate package entries",
            "action": "Edit requirements-lock.txt to remove duplicates",
        })

    if not conflicts_ok:
        report["recommendations"].append({
            "priority": "high",
            "message": "Resolve dependency conflicts",
            "action": f"Review: {conflicts_msg[:200]}",
        })

    if outdated:
        report["recommendations"].append({
            "priority": "medium",
            "message": f"Update {len(outdated)} outdated packages",
            "action": "Run: pip list --outdated",
        })

    if not hashes_ok:
        report["recommendations"].append({
            "priority": "medium",
            "message": "Add hash verification for supply chain security",
            "action": "Run: python scripts/lock_dependencies.py --with-hashes",
        })

    return report


def print_human_report(report: Dict):
    """Print human-readable report to console."""
    print("\n" + "=" * 70)
    print("DEPENDENCY SECURITY AUDIT REPORT")
    print("=" * 70)
    print(f"Generated: {report['generated_at']}")
    print(f"Python: {report['python_version']}")
    print("-" * 70)

    summary = report['summary']
    print(f"\nSUMMARY:")
    print(f"  Total packages:        {summary['total_packages']}")
    print(f"  Abstract requirements: {summary['abstract_requirements']}")
    print(f"  Vulnerabilities:       {summary['vulnerability_count']}")
    print(f"  Outdated packages:     {summary['outdated_count']}")
    print(f"  Duplicates:            {summary['duplicate_count']}")
    print(f"  Dependency conflicts:  {'Yes' if summary['has_conflicts'] else 'No'}")
    print(f"  Hash verification:     {'Passed' if summary['hashes_verified'] else 'Failed'}")

    # Vulnerabilities
    if report['vulnerabilities']:
        print(f"\n{'!'*70}")
        print(f"VULNERABILITIES FOUND: {len(report['vulnerabilities'])}")
        print(f"{'!'*70}")
        for vuln in report['vulnerabilities']:
            print(f"\n  Package: {vuln['package']}=={vuln['version']}")
            print(f"  ID: {vuln['vuln_id']}")
            if vuln.get('description'):
                print(f"  Description: {vuln['description'][:100]}...")
            if vuln.get('fix_version'):
                print(f"  Fix: upgrade to {vuln['fix_version']}")
    else:
        print(f"\n[OK] No known vulnerabilities found")

    # Outdated
    if report['outdated']:
        print(f"\n{'─'*70}")
        print(f"OUTDATED PACKAGES: {len(report['outdated'])}")
        print(f"{'─'*70}")
        for pkg in report['outdated']:
            print(f"  {pkg['package']}: {pkg['installed']} -> {pkg['latest']}")

    # Duplicates
    if report['duplicates']:
        print(f"\n{'─'*70}")
        print(f"DUPLICATE PACKAGES: {len(report['duplicates'])}")
        print(f"{'─'*70}")
        for dup in report['duplicates']:
            print(f"  {dup['package']}: {', '.join(dup['versions'])}")

    # Conflicts
    if report['conflicts']['ok']:
        print(f"\n[OK] No dependency conflicts detected")
    else:
        print(f"\n[FAIL] Dependency conflicts detected:")
        print(f"  {report['conflicts']['message'][:300]}")

    # Hash verification
    if report['hash_verification']['verified']:
        print(f"\n[OK] Hash verification passed")
    else:
        print(f"\n[WARN] Hash verification issues:")
        for issue in report['hash_verification']['issues']:
            print(f"  - {issue}")

    # Recommendations
    if report['recommendations']:
        print(f"\n{'='*70}")
        print("RECOMMENDATIONS:")
        print(f"{'='*70}")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"\n{rec['priority'].upper()}: {rec['message']}")
            print(f"  Action: {rec['action']}")

    print(f"\n{'='*70}")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Audit dependencies for security issues"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix vulnerabilities automatically"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORT_FILE,
        help="Output path for JSON report"
    )
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Skip pip-audit (faster, less comprehensive)"
    )
    parser.add_argument(
        "--skip-outdated",
        action="store_true",
        help="Skip outdated package check"
    )

    args = parser.parse_args()

    # Parse lock file
    print(f"Reading {REQUIREMENTS_LOCK}...")
    packages = parse_lock_file(REQUIREMENTS_LOCK)

    if not packages:
        print("Error: No packages found in lock file")
        sys.exit(1)

    # Parse abstract requirements
    abstract_reqs = parse_in_file(REQUIREMENTS_IN)

    # Run checks
    print("Checking for duplicates...")
    duplicates = check_duplicates(packages)

    print("Verifying hashes...")
    hashes_ok, hash_issues = verify_hashes(REQUIREMENTS_LOCK)

    print("Checking for dependency conflicts...")
    conflicts_ok, conflicts_msg = check_conflicts(packages)

    vulns = []
    if not args.skip_audit:
        print("Running security audit (pip-audit)...")
        vulns = check_pip_audit(packages)
    else:
        print("Skipping security audit (--skip-audit)")

    outdated = []
    if not args.skip_outdated:
        print("Checking for outdated packages...")
        outdated = check_outdated(packages)
    else:
        print("Skipping outdated check (--skip-outdated)")

    # Generate report
    report = generate_report(
        packages, abstract_reqs, vulns, outdated,
        duplicates, conflicts_ok, conflicts_msg,
        hashes_ok, hash_issues
    )

    # Output
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_human_report(report)

    # Save JSON report
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {args.output}")

    # Fix mode
    if args.fix and vulns:
        print("\nAttempting to fix vulnerabilities...")
        for vuln in vulns:
            if vuln.get('fix_version'):
                print(f"  Upgrading {vuln['package']} to {vuln['fix_version']}...")
                try:
                    subprocess.run(
                        ["pip", "install", "--upgrade", f"{vuln['package']}=={vuln['fix_version']}"],
                        check=True
                    )
                except subprocess.CalledProcessError as e:
                    print(f"  Failed to upgrade {vuln['package']}: {e}")

    # Exit code
    if vulns or duplicates or not conflicts_ok:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
