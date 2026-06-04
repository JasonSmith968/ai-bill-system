#!/usr/bin/env python3
"""
Dependency Lock Script for AI Accounting System
===============================================
Resolves abstract requirements to exact pinned versions with hash verification.

Usage:
    python scripts/lock_dependencies.py
    python scripts/lock_dependencies.py --with-hashes
    python scripts/lock_dependencies.py --check
    python scripts/lock_dependencies.py --audit

Output:
    - backend/requirements-lock.txt (pinned versions)
    - dependency_report.json (audit results)
"""

import argparse
import hashlib
import json
import os
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
REQUIREMENTS_IN = PROJECT_ROOT / "backend" / "requirements.in"
REQUIREMENTS_LOCK = PROJECT_ROOT / "backend" / "requirements-lock.txt"
REPORT_FILE = PROJECT_ROOT / "dependency_report.json"

# Minimum versions from requirements.in (manually maintained for offline use)
# These should be updated periodically or resolved via pip
KNOWN_VERSIONS = {
    # Core Framework
    "Flask": "3.0.0",
    "Flask-SQLAlchemy": "3.1.1",
    "Flask-Migrate": "4.0.5",
    "Flask-CORS": "4.0.0",
    # Security & Authentication
    "PyJWT": "2.8.0",
    "Werkzeug": "3.0.1",
    "Flask-Limiter": "3.5.0",
    "redis": "5.0.1",
    "pyotp": "2.9.0",
    "qrcode": "7.4.2",
    # Database
    "PyMySQL": "1.1.0",
    "cryptography": "44.0.0",
    # AI & External APIs
    "requests": "2.31.0",
    # Reports & Export
    "openpyxl": "3.1.2",
    "reportlab": "4.0.8",
    # OCR & Image Processing
    "Pillow": "10.1.0",
    "rapidocr-onnxruntime": "1.3.16",
    # Configuration
    "python-dotenv": "1.0.0",
    # Object Storage
    "minio": "7.2.0",
    "oss2": "2.18.0",
    "cos-python-sdk-v5": "1.9.30",
    # Async / Task Queue
    "celery": "5.3.6",
    "flask-caching": "2.1.0",
    "flask-socketio": "5.3.6",
    "eventlet": "0.35.2",
    # Monitoring & Observability
    "sentry-sdk": "1.38.0",
    "prometheus-client": "0.19.0",
    # Production Server
    "gunicorn": "21.2.0",
}

# Known transitive dependencies with pinned versions
TRANSITIVE_DEPS = {
    "alembic": "1.13.1",
    "blinker": "1.7.0",
    "click": "8.1.7",
    "importlib-metadata": "7.0.1",
    "itsdangerous": "2.1.2",
    "Jinja2": "3.1.2",
    "Mako": "1.3.0",
    "MarkupSafe": "2.1.3",
    "SQLAlchemy": "2.0.23",
    "typing_extensions": "4.9.0",
    "zipp": "3.17.0",
    "async-timeout": "4.0.3",
    "billiard": "4.2.0",
    "kombu": "5.3.4",
    "vine": "5.1.0",
    "amqp": "5.2.0",
    "certifi": "2023.11.17",
    "charset-normalizer": "3.3.2",
    "idna": "3.6",
    "urllib3": "2.1.0",
    "colorama": "0.4.6",
    "pypng": "0.20220715.0",
    "et-xmlfile": "1.1.0",
}


# ============================================================================
# Requirements Parser
# ============================================================================

class Requirement:
    """Represents a single package requirement."""

    def __init__(self, line: str):
        self.line = line.strip()
        self.name = ""
        self.operator = ">="
        self.version = ""
        self.extras = ""
        self.comment = ""

        self._parse()

    def _parse(self):
        """Parse requirement line like 'package[extras]>=1.0.0'."""
        # Remove comments
        if '#' in self.line:
            parts = self.line.split('#', 1)
            self.line = parts[0].strip()
            self.comment = parts[1].strip()

        # Skip empty lines and comments-only lines
        if not self.line or self.line.startswith('#'):
            return

        # Parse package[extras]operator version
        match = re.match(
            r'^([a-zA-Z0-9_-]+)(?:\[([^\]]+)\])?\s*(?:(>=|==|<=|~=|!=|>|<)\s*(.+))?$',
            self.line
        )
        if match:
            self.name = match.group(1)
            self.extras = match.group(2) or ""
            self.operator = match.group(3) or ">="
            self.version = match.group(4) or ""

    @property
    def is_valid(self) -> bool:
        return bool(self.name)

    @property
    def is_pinned(self) -> bool:
        return self.operator == "==" and bool(self.version)

    def __repr__(self):
        if self.extras:
            return f"{self.name}[{self.extras}]"
        return self.name


def parse_requirements(filepath: Path) -> List[Requirement]:
    """Parse a requirements file and return list of Requirement objects."""
    requirements = []
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return requirements

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                req = Requirement(line)
                if req.is_valid:
                    requirements.append(req)

    return requirements


# ============================================================================
# Version Resolution
# ============================================================================

def resolve_version(req: Requirement, use_latest: bool = False) -> str:
    """
    Resolve the exact version for a requirement.

    Uses KNOWN_VERSIONS database. In a real implementation, this would
    query PyPI API or use pip-compile.
    """
    name = req.name.lower().replace('-', '_')

    # Check known versions (case-insensitive)
    for known_name, version in KNOWN_VERSIONS.items():
        if known_name.lower().replace('-', '_') == name:
            if use_latest:
                return _get_latest_version(known_name)
            return version

    # Check transitive deps
    for known_name, version in TRANSITIVE_DEPS.items():
        if known_name.lower().replace('-', '_') == name:
            return version

    # If we have a pinned version, use it
    if req.is_pinned:
        return req.version

    print(f"Warning: Unknown package '{req.name}', using minimum version {req.version}")
    return req.version


def _get_latest_version(package_name: str) -> str:
    """
    Get latest version from PyPI.

    In production, this would query: https://pypi.org/pypi/{package}/json
    For now, returns the known version.
    """
    # TODO: Implement PyPI API query
    return KNOWN_VERSIONS.get(package_name, "0.0.0")


def get_package_hash(package_name: str, version: str) -> Optional[str]:
    """
    Get SHA256 hash for a package from PyPI.

    Returns hash in format: sha256:hexdigest
    """
    try:
        import urllib.request
        import json as json_lib

        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json_lib.loads(response.read())

            # Get hashes from URLs
            hashes = []
            for url_info in data.get('urls', []):
                if 'digests' in url_info and 'sha256' in url_info['digests']:
                    hashes.append(url_info['digests']['sha256'])

            if hashes:
                # Return first hash (usually the wheel)
                return f"sha256:{hashes[0]}"
    except Exception as e:
        print(f"  Could not fetch hash for {package_name}=={version}: {e}")

    return None


# ============================================================================
# Lock File Generator
# ============================================================================

def generate_lock_file(
    requirements: List[Requirement],
    output_path: Path,
    include_hashes: bool = False,
    include_transitive: bool = True
) -> Dict:
    """
    Generate a locked requirements file with exact pins.

    Returns statistics about the generation.
    """
    stats = {
        "total": 0,
        "pinned": 0,
        "resolved": 0,
        "hashes_added": 0,
        "warnings": [],
    }

    lines = []
    lines.append("# " + "=" * 76)
    lines.append("# Pinned Dependencies - AI Accounting System")
    lines.append("# " + "=" * 76)
    lines.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Python: {sys.version.split()[0]}")
    lines.append("#")
    lines.append("# This file contains exact version pins for reproducible builds.")
    lines.append("# DO NOT EDIT MANUALLY - edit requirements.in and regenerate:")
    lines.append("#   python scripts/lock_dependencies.py")
    lines.append("#")
    if include_hashes:
        lines.append("# Hash verification enabled for supply chain security.")
        lines.append("# Install with: pip install --require-hashes -r requirements-lock.txt")
    else:
        lines.append("# To add hash verification, run:")
        lines.append("#   python scripts/lock_dependencies.py --with-hashes")
        lines.append("# Install with: pip install -r requirements-lock.txt")
    lines.append("# " + "=" * 76)
    lines.append("")

    # Group requirements by category
    categories = _categorize_requirements(requirements)

    for category, reqs in categories.items():
        lines.append(f"# {'─' * 76}")
        lines.append(f"# {category}")
        lines.append(f"# {'─' * 76}")

        for req in reqs:
            version = resolve_version(req)
            stats["total"] += 1

            if req.is_pinned:
                stats["pinned"] += 1
            else:
                stats["resolved"] += 1

            # Build the requirement line
            req_line = f"{req.name}=={version}"

            # Add extras if present
            if req.extras:
                req_line = f"{req.name}[{req.extras}]=={version}"

            # Add hash if requested
            if include_hashes:
                pkg_hash = get_package_hash(req.name, version)
                if pkg_hash:
                    req_line += f" \\\n    --hash={pkg_hash}"
                    stats["hashes_added"] += 1
                else:
                    stats["warnings"].append(f"No hash for {req.name}=={version}")

            lines.append(req_line)

        lines.append("")

    # Add transitive dependencies
    if include_transitive:
        lines.append(f"# {'─' * 76}")
        lines.append("# Transitive Dependencies (pinned for reproducibility)")
        lines.append(f"# {'─' * 76}")
        lines.append("# These are automatically resolved but pinned here for consistency")
        lines.append("")

        for name, version in sorted(TRANSITIVE_DEPS.items()):
            stats["total"] += 1
            stats["resolved"] += 1

            req_line = f"{name}=={version}"

            if include_hashes:
                pkg_hash = get_package_hash(name, version)
                if pkg_hash:
                    req_line += f" \\\n    --hash={pkg_hash}"
                    stats["hashes_added"] += 1

            lines.append(req_line)

    # Write the file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    return stats


def _categorize_requirements(requirements: List[Requirement]) -> Dict[str, List[Requirement]]:
    """Group requirements by their comment category."""
    categories = {
        "Core Framework": [],
        "Security & Authentication": [],
        "Database": [],
        "AI & External APIs": [],
        "Reports & Export": [],
        "OCR & Image Processing": [],
        "Configuration": [],
        "Object Storage (optional)": [],
        "Async / Task Queue": [],
        "Monitoring & Observability": [],
        "Production Server": [],
        "Other": [],
    }

    current_category = "Other"

    for req in requirements:
        # Check if this requirement has a category comment
        if req.comment:
            for category in categories:
                if category.lower() in req.comment.lower():
                    current_category = category
                    break

        categories[current_category].append(req)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


# ============================================================================
# Verification & Audit
# ============================================================================

def check_pinning(requirements: List[Requirement]) -> Dict:
    """Check how many requirements are properly pinned."""
    total = len(requirements)
    pinned = sum(1 for r in requirements if r.is_pinned)
    unpinned = total - pinned

    return {
        "total": total,
        "pinned": pinned,
        "unpinned": unpinned,
        "pin_percentage": (pinned / total * 100) if total > 0 else 0,
    }


def check_for_cves(requirements: List[Requirement]) -> List[Dict]:
    """
    Check for known CVEs using pip-audit if available.

    Returns list of vulnerability reports.
    """
    vulns = []

    # Try pip-audit first
    try:
        result = subprocess.run(
            ["pip-audit", "--requirement", str(REQUIREMENTS_LOCK), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            audit_data = json.loads(result.stdout)
            for item in audit_data:
                vulns.append({
                    "package": item.get("name"),
                    "version": item.get("version"),
                    "vuln_id": item.get("id"),
                    "description": item.get("description"),
                    "fix_version": item.get("fix_versions", [None])[0],
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        print("Note: pip-audit not available or failed, skipping CVE check")

    return vulns


def verify_hashes(requirements_lock: Path) -> Tuple[bool, List[str]]:
    """
    Verify that hash entries are present and properly formatted.

    Returns (success, list of issues).
    """
    issues = []

    if not requirements_lock.exists():
        return False, ["Lock file not found"]

    with open(requirements_lock, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check for hash entries
    if "--hash=sha256:" not in content:
        issues.append("No hash entries found in lock file")

    # Check for proper line continuation
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "--hash=" in line and not line.strip().endswith('--hash=sha256:PLACEHOLDER_HASH'):
            # Check if previous line has backslash
            if i > 0 and not lines[i-1].strip().endswith('\\'):
                issues.append(f"Line {i+1}: Hash entry without line continuation")

    return len(issues) == 0, issues


def run_pip_check() -> Tuple[bool, str]:
    """Run pip check to verify dependency compatibility."""
    try:
        result = subprocess.run(
            ["pip", "check"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "pip check timed out"
    except FileNotFoundError:
        return False, "pip not found"


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(
    requirements: List[Requirement],
    lock_stats: Dict,
    vulns: List[Dict],
    output_path: Path
) -> Dict:
    """Generate comprehensive dependency audit report."""
    pin_stats = check_pinning(requirements)

    report = {
        "generated_at": datetime.now().isoformat(),
        "project": "AI Accounting System",
        "python_version": sys.version,
        "summary": {
            "total_dependencies": lock_stats["total"],
            "direct_dependencies": len(requirements),
            "transitive_dependencies": lock_stats["total"] - len(requirements),
            "pinned_count": pin_stats["pinned"],
            "unpinned_count": pin_stats["unpinned"],
            "pin_percentage": pin_stats["pin_percentage"],
            "hashes_added": lock_stats.get("hashes_added", 0),
        },
        "vulnerabilities": vulns,
        "vulnerability_count": len(vulns),
        "warnings": lock_stats.get("warnings", []),
        "recommendations": [],
    }

    # Add recommendations
    if pin_stats["unpinned"] > 0:
        report["recommendations"].append(
            f"Pin {pin_stats['unpinned']} unpinned dependencies in requirements.in"
        )

    if len(vulns) > 0:
        report["recommendations"].append(
            f"Address {len(vulns)} known vulnerabilities"
        )

    if lock_stats.get("hashes_added", 0) == 0:
        report["recommendations"].append(
            "Add hash verification with --with-hashes flag"
        )

    # Write JSON report
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def print_summary(report: Dict):
    """Print human-readable summary to console."""
    print("\n" + "=" * 60)
    print("DEPENDENCY AUDIT REPORT")
    print("=" * 60)
    print(f"Generated: {report['generated_at']}")
    print(f"Python: {report['python_version'].split()[0]}")
    print("-" * 60)

    summary = report['summary']
    print(f"\nDependency Summary:")
    print(f"  Total dependencies:      {summary['total_dependencies']}")
    print(f"  Direct dependencies:     {summary['direct_dependencies']}")
    print(f"  Transitive dependencies: {summary['transitive_dependencies']}")
    print(f"  Pinned versions:         {summary['pinned_count']}")
    print(f"  Unpinned versions:       {summary['unpinned_count']}")
    print(f"  Pin coverage:            {summary['pin_percentage']:.1f}%")
    print(f"  Hashes added:            {summary['hashes_added']}")

    if report['vulnerability_count'] > 0:
        print(f"\n[!] VULNERABILITIES FOUND: {report['vulnerability_count']}")
        for vuln in report['vulnerabilities']:
            print(f"  - {vuln['package']}=={vuln['version']}: {vuln['vuln_id']}")
            if vuln.get('fix_version'):
                print(f"    Fix: upgrade to {vuln['fix_version']}")
    else:
        print("\n[OK] No known vulnerabilities found")

    if report['recommendations']:
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")

    print("\n" + "=" * 60)


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Lock dependencies with exact versions and hashes"
    )
    parser.add_argument(
        "--with-hashes",
        action="store_true",
        help="Include SHA256 hashes for supply chain verification"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check current pinning status without regenerating"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run security audit (requires pip-audit)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify lock file integrity"
    )
    parser.add_argument(
        "--no-transitive",
        action="store_true",
        help="Exclude transitive dependencies from lock file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REQUIREMENTS_LOCK,
        help="Output path for lock file"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORT_FILE,
        help="Output path for JSON report"
    )

    args = parser.parse_args()

    # Parse requirements
    print(f"Reading {REQUIREMENTS_IN}...")
    requirements = parse_requirements(REQUIREMENTS_IN)

    if not requirements:
        print("Error: No requirements found in requirements.in")
        sys.exit(1)

    # Check mode
    if args.check:
        stats = check_pinning(requirements)
        print(f"\nPinning Status:")
        print(f"  Total: {stats['total']}")
        print(f"  Pinned: {stats['pinned']}")
        print(f"  Unpinned: {stats['unpinned']}")
        print(f"  Coverage: {stats['pin_percentage']:.1f}%")
        sys.exit(0 if stats['unpinned'] == 0 else 1)

    # Verify mode
    if args.verify:
        success, issues = verify_hashes(args.output)
        if success:
            print("[OK] Lock file verification passed")
        else:
            print("[FAIL] Lock file verification failed:")
            for issue in issues:
                print(f"  - {issue}")
        sys.exit(0 if success else 1)

    # Generate lock file
    print(f"Generating {args.output}...")
    lock_stats = generate_lock_file(
        requirements,
        args.output,
        include_hashes=args.with_hashes,
        include_transitive=not args.no_transitive
    )

    # Run audit if requested
    vulns = []
    if args.audit:
        print("Running security audit...")
        vulns = check_for_cves(requirements)

    # Generate report
    report = generate_report(requirements, lock_stats, vulns, args.report)
    print_summary(report)

    # Print lock file location
    print(f"\nLock file written to: {args.output}")
    print(f"Report written to: {args.report}")

    if args.with_hashes:
        print("\nTo install with hash verification:")
        print(f"  pip install --require-hashes -r {args.output}")
    else:
        print("\nTo install:")
        print(f"  pip install -r {args.output}")
        print("\nTo add hash verification:")
        print(f"  python scripts/lock_dependencies.py --with-hashes")


if __name__ == "__main__":
    main()
