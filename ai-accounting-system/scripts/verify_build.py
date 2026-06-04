#!/usr/bin/env python3
"""
Build Reproducibility Verification Script
==========================================
Creates a temporary virtual environment and verifies that all
dependencies can be installed correctly from the lock file.

Usage:
    python scripts/verify_build.py
    python scripts/verify_build.py --clean
    python scripts/verify_build.py --no-venv

Exit Codes:
    0 - All verifications passed
    1 - Verification failed
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
REQUIREMENTS_LOCK = PROJECT_ROOT / "backend" / "requirements-lock.txt"
REQUIREMENTS_IN = PROJECT_ROOT / "backend" / "requirements.in"
VERIFY_VENV = PROJECT_ROOT / ".verify_venv"


# ============================================================================
# Verification Steps
# ============================================================================

def check_prerequisites() -> Tuple[bool, List[str]]:
    """Check that required tools are available."""
    issues = []

    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"Python 3.8+ required, found {sys.version}")

    # Check pip
    try:
        import pip
    except ImportError:
        issues.append("pip not found")

    # Check venv module
    try:
        import venv
    except ImportError:
        issues.append("venv module not available")

    return len(issues) == 0, issues


def check_files_exist() -> Tuple[bool, List[str]]:
    """Check that required files exist."""
    issues = []

    if not REQUIREMENTS_LOCK.exists():
        issues.append(f"Lock file not found: {REQUIREMENTS_LOCK}")

    if not REQUIREMENTS_IN.exists():
        issues.append(f"Requirements.in not found: {REQUIREMENTS_IN}")

    return len(issues) == 0, issues


def create_virtual_env(venv_path: Path) -> Tuple[bool, str]:
    """Create a temporary virtual environment."""
    try:
        # Remove existing venv if present
        if venv_path.exists():
            shutil.rmtree(venv_path)

        # Create new venv
        venv.create(venv_path, with_pip=True)
        return True, "Virtual environment created"
    except Exception as e:
        return False, f"Failed to create venv: {e}"


def get_venv_python(venv_path: Path) -> Path:
    """Get path to Python executable in venv."""
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def get_venv_pip(venv_path: Path) -> Path:
    """Get path to pip executable in venv."""
    if sys.platform == "win32":
        return venv_path / "Scripts" / "pip.exe"
    return venv_path / "bin" / "pip"


def install_requirements(venv_path: Path, requirements_file: Path) -> Tuple[bool, str]:
    """Install requirements from file into venv."""
    pip_path = get_venv_pip(venv_path)

    if not pip_path.exists():
        return False, f"pip not found at {pip_path}"

    try:
        # Upgrade pip first
        subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Install requirements
        result = subprocess.run(
            [str(pip_path), "install", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )

        if result.returncode == 0:
            return True, "Requirements installed successfully"
        else:
            return False, f"Installation failed:\n{result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Installation timed out (10 minutes)"
    except Exception as e:
        return False, f"Installation error: {e}"


def verify_packages_installed(venv_path: Path, requirements_file: Path) -> Tuple[bool, Dict]:
    """Verify all packages from lock file are installed."""
    python_path = get_venv_python(venv_path)
    results = {"installed": [], "missing": [], "version_mismatch": []}

    # Parse requirements
    packages = parse_requirements(requirements_file)

    for pkg_name, pkg_version in packages:
        # Check if package is installed
        try:
            result = subprocess.run(
                [str(python_path), "-c", f"import {pkg_name.replace('-', '_')}; print({pkg_name.replace('-', '_')}.__version__)"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                installed_version = result.stdout.strip()
                if installed_version == pkg_version:
                    results["installed"].append(pkg_name)
                else:
                    results["version_mismatch"].append({
                        "package": pkg_name,
                        "expected": pkg_version,
                        "actual": installed_version,
                    })
            else:
                results["missing"].append(pkg_name)

        except (subprocess.TimeoutExpired, Exception):
            results["missing"].append(pkg_name)

    success = len(results["missing"]) == 0 and len(results["version_mismatch"]) == 0
    return success, results


def run_pip_check(venv_path: Path) -> Tuple[bool, str]:
    """Run pip check to verify dependency compatibility."""
    pip_path = get_venv_pip(venv_path)

    try:
        result = subprocess.run(
            [str(pip_path), "check"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            return True, "All dependencies compatible"
        else:
            return False, f"Dependency conflicts:\n{result.stdout}\n{result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "pip check timed out"
    except Exception as e:
        return False, f"pip check failed: {e}"


def run_import_tests(venv_path: Path) -> Tuple[bool, Dict]:
    """Test importing key packages."""
    python_path = get_venv_python(venv_path)
    results = {"passed": [], "failed": []}

    # Key packages to test
    test_imports = [
        "flask",
        "sqlalchemy",
        "redis",
        "celery",
        "requests",
        "jwt",
        "PIL",
        "openpyxl",
    ]

    for module in test_imports:
        try:
            result = subprocess.run(
                [str(python_path), "-c", f"import {module}"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                results["passed"].append(module)
            else:
                results["failed"].append({
                    "module": module,
                    "error": result.stderr.strip(),
                })

        except Exception as e:
            results["failed"].append({
                "module": module,
                "error": str(e),
            })

    success = len(results["failed"]) == 0
    return success, results


def parse_requirements(filepath: Path) -> List[Tuple[str, str]]:
    """Parse requirements file and return list of (name, version) tuples."""
    packages = []

    if not filepath.exists():
        return packages

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
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
            import re
            match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[([^\]]+)\])?==(.+)$', line)
            if match:
                packages.append((match.group(1), match.group(3).strip()))

    return packages


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(
    venv_ok: bool,
    venv_msg: str,
    install_ok: bool,
    install_msg: str,
    verify_ok: bool,
    verify_results: Dict,
    check_ok: bool,
    check_msg: str,
    import_ok: bool,
    import_results: Dict
) -> Dict:
    """Generate verification report."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "python_version": sys.version,
        "venv_path": str(VERIFY_VENV),
        "results": {
            "venv_creation": {"success": venv_ok, "message": venv_msg},
            "installation": {"success": install_ok, "message": install_msg},
            "verification": {"success": verify_ok, "details": verify_results},
            "pip_check": {"success": check_ok, "message": check_msg},
            "import_tests": {"success": import_ok, "details": import_results},
        },
        "overall_success": all([venv_ok, install_ok, verify_ok, check_ok, import_ok]),
    }

    return report


def print_report(report: Dict):
    """Print human-readable report."""
    print("\n" + "=" * 70)
    print("BUILD REPRODUCIBILITY VERIFICATION REPORT")
    print("=" * 70)
    print(f"Generated: {report['generated_at']}")
    print(f"Python: {report['python_version'].split()[0]}")
    print(f"Venv: {report['venv_path']}")
    print("-" * 70)

    results = report['results']

    # Venv creation
    status = "[OK]" if results['venv_creation']['success'] else "[FAIL]"
    print(f"\n{status} Virtual Environment: {results['venv_creation']['message']}")

    # Installation
    status = "[OK]" if results['installation']['success'] else "[FAIL]"
    print(f"{status} Installation: {results['installation']['message']}")

    # Verification
    status = "[OK]" if results['verification']['success'] else "[FAIL]"
    print(f"{status} Package Verification:")
    details = results['verification']['details']
    print(f"    Installed: {len(details['installed'])}")
    print(f"    Missing: {len(details['missing'])}")
    print(f"    Version mismatch: {len(details['version_mismatch'])}")

    if details['missing']:
        print(f"    Missing packages: {', '.join(details['missing'])}")
    if details['version_mismatch']:
        for mismatch in details['version_mismatch']:
            print(f"    Mismatch: {mismatch['package']} (expected {mismatch['expected']}, got {mismatch['actual']})")

    # Pip check
    status = "[OK]" if results['pip_check']['success'] else "[FAIL]"
    print(f"{status} Dependency Check: {results['pip_check']['message']}")

    # Import tests
    status = "[OK]" if results['import_tests']['success'] else "[FAIL]"
    print(f"{status} Import Tests:")
    import_details = results['import_tests']['details']
    print(f"    Passed: {len(import_details['passed'])}")
    print(f"    Failed: {len(import_details['failed'])}")

    if import_details['failed']:
        for failure in import_details['failed']:
            print(f"    Failed: {failure['module']} - {failure['error'][:50]}")

    # Overall result
    print("\n" + "=" * 70)
    if report['overall_success']:
        print("[OK] BUILD VERIFICATION PASSED")
        print("All dependencies can be installed reproducibly.")
    else:
        print("[FAIL] BUILD VERIFICATION FAILED")
        print("Some dependencies could not be installed correctly.")
    print("=" * 70)


# ============================================================================
# Cleanup
# ============================================================================

def cleanup(venv_path: Path):
    """Remove temporary virtual environment."""
    if venv_path.exists():
        try:
            shutil.rmtree(venv_path)
            print(f"\nCleaned up: {venv_path}")
        except Exception as e:
            print(f"\nWarning: Could not remove {venv_path}: {e}")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Verify build reproducibility"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean up temporary venv after verification"
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Use current environment instead of creating new venv"
    )
    parser.add_argument(
        "--keep-venv",
        action="store_true",
        help="Keep venv after verification (for debugging)"
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip installation (use existing venv)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("BUILD REPRODUCIBILITY VERIFICATION")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")

    # Check prerequisites
    print("\nChecking prerequisites...")
    prereq_ok, prereq_issues = check_prerequisites()
    if not prereq_ok:
        print("Prerequisites not met:")
        for issue in prereq_issues:
            print(f"  - {issue}")
        sys.exit(1)

    # Check files
    print("Checking required files...")
    files_ok, file_issues = check_files_exist()
    if not files_ok:
        print("Required files missing:")
        for issue in file_issues:
            print(f"  - {issue}")
        sys.exit(1)

    # Determine venv path
    if args.no_venv:
        venv_path = Path(sys.prefix)
        print(f"\nUsing current environment: {venv_path}")
        venv_ok, venv_msg = True, "Using current environment"
    else:
        venv_path = VERIFY_VENV
        print(f"\nCreating virtual environment: {venv_path}")
        venv_ok, venv_msg = create_virtual_env(venv_path)
        if not venv_ok:
            print(f"Failed: {venv_msg}")
            sys.exit(1)
        print(f"[OK] {venv_msg}")

    # Install requirements
    install_ok, install_msg = True, "Skipped"
    if not args.skip_install:
        print("\nInstalling requirements...")
        install_ok, install_msg = install_requirements(venv_path, REQUIREMENTS_LOCK)
        if install_ok:
            print(f"[OK] {install_msg}")
        else:
            print(f"[FAIL] {install_msg}")
    else:
        print("\nSkipping installation (--skip-install)")

    # Verify packages
    print("\nVerifying installed packages...")
    verify_ok, verify_results = verify_packages_installed(venv_path, REQUIREMENTS_LOCK)
    print(f"[OK] Installed: {len(verify_results['installed'])}")
    if verify_results['missing']:
        print(f"[FAIL] Missing: {len(verify_results['missing'])}")
    if verify_results['version_mismatch']:
        print(f"[FAIL] Version mismatch: {len(verify_results['version_mismatch'])}")

    # Run pip check
    print("\nRunning pip check...")
    check_ok, check_msg = run_pip_check(venv_path)
    if check_ok:
        print(f"[OK] {check_msg}")
    else:
        print(f"[FAIL] {check_msg}")

    # Run import tests
    print("\nRunning import tests...")
    import_ok, import_results = run_import_tests(venv_path)
    print(f"[OK] Passed: {len(import_results['passed'])}")
    if import_results['failed']:
        print(f"[FAIL] Failed: {len(import_results['failed'])}")

    # Generate report
    report = generate_report(
        venv_ok, venv_msg, install_ok, install_msg,
        verify_ok, verify_results, check_ok, check_msg,
        import_ok, import_results
    )

    print_report(report)

    # Save report
    report_file = PROJECT_ROOT / "build_verification_report.json"
    import json
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_file}")

    # Cleanup
    if args.clean or (not args.keep_venv and not args.no_venv):
        cleanup(venv_path)

    # Exit code
    sys.exit(0 if report['overall_success'] else 1)


if __name__ == "__main__":
    main()
