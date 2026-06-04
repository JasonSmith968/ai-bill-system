# Dependency Management Guide

## Overview

This document describes the dependency management system for the AI Accounting System. The system ensures reproducible builds, supply chain security, and automated vulnerability detection.

## File Structure

```
backend/
├── requirements.in          # Abstract requirements (what we want)
├── requirements.txt         # Legacy file (references lock file)
└── requirements-lock.txt    # Pinned versions with hashes (use this)

scripts/
├── lock_dependencies.py     # Generate lock file
├── dependency_audit.py      # Security audit
└── verify_build.py          # Build verification
```

## Quick Start

### Installing Dependencies

**For Development (without hash verification):**
```bash
pip install -r backend/requirements-lock.txt
```

**For Production (with hash verification):**
```bash
pip install --require-hashes -r backend/requirements-lock.txt
```

### Adding a New Dependency

1. **Add to `requirements.in`:**
   ```python
   # Add under the appropriate section
   new-package>=1.0.0
   ```

2. **Update version database in `lock_dependencies.py`:**
   ```python
   KNOWN_VERSIONS = {
       # ... existing packages ...
       "new-package": "1.2.3",  # Add exact version
   }
   ```

3. **Regenerate lock file:**
   ```bash
   python scripts/lock_dependencies.py
   ```

4. **Verify the change:**
   ```bash
   python scripts/verify_build.py
   ```

### Updating Dependencies

1. **Check for outdated packages:**
   ```bash
   python scripts/dependency_audit.py --skip-audit
   ```

2. **Update version in `lock_dependencies.py`:**
   ```python
   KNOWN_VERSIONS = {
       "package-name": "2.0.0",  # Update version
   }
   ```

3. **Regenerate lock file:**
   ```bash
   python scripts/lock_dependencies.py
   ```

4. **Run security audit:**
   ```bash
   python scripts/dependency_audit.py
   ```

5. **Verify build:**
   ```bash
   python scripts/verify_build.py
   ```

## Script Usage

### lock_dependencies.py

Generates the pinned lock file from abstract requirements.

```bash
# Basic usage - generate lock file
python scripts/lock_dependencies.py

# With hash verification (recommended for production)
python scripts/lock_dependencies.py --with-hashes

# Check current pinning status
python scripts/lock_dependencies.py --check

# Verify lock file integrity
python scripts/lock_dependencies.py --verify

# Run security audit after locking
python scripts/lock_dependencies.py --audit

# Custom output paths
python scripts/lock_dependencies.py --output custom-lock.txt --report custom-report.json
```

**Options:**
- `--with-hashes`: Include SHA256 hashes for supply chain verification
- `--check`: Check pinning status without regenerating
- `--audit`: Run security audit (requires pip-audit)
- `--verify`: Verify lock file integrity
- `--no-transitive`: Exclude transitive dependencies
- `--output PATH`: Custom output path for lock file
- `--report PATH`: Custom output path for JSON report

### dependency_audit.py

Checks for known vulnerabilities and dependency issues.

```bash
# Full audit
python scripts/dependency_audit.py

# Output as JSON (for CI)
python scripts/dependency_audit.py --json

# Skip slow checks
python scripts/dependency_audit.py --skip-audit --skip-outdated

# Attempt to fix vulnerabilities
python scripts/dependency_audit.py --fix
```

**Options:**
- `--json`: Output report as JSON
- `--fix`: Attempt to fix vulnerabilities automatically
- `--output PATH`: Custom output path for report
- `--skip-audit`: Skip pip-audit (faster)
- `--skip-outdated`: Skip outdated package check

### verify_build.py

Verifies that dependencies can be installed reproducibly.

```bash
# Full verification (creates temporary venv)
python scripts/verify_build.py

# Use current environment
python scripts/verify_build.py --no-venv

# Keep venv for debugging
python scripts/verify_build.py --keep-venv

# Skip installation (use existing venv)
python scripts/verify_build.py --skip-install

# Clean up after verification
python scripts/verify_build.py --clean
```

**Options:**
- `--clean`: Clean up temporary venv after verification
- `--no-venv`: Use current environment instead of creating new venv
- `--keep-venv`: Keep venv after verification (for debugging)
- `--skip-install`: Skip installation (use existing venv)

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/dependencies.yml`:

```yaml
name: Dependency Security

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    # Run weekly on Monday at 9:00 AM
    - cron: '0 9 * * 1'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install pip-audit
        run: pip install pip-audit

      - name: Run dependency audit
        run: python scripts/dependency_audit.py --json --output audit-report.json

      - name: Upload audit report
        uses: actions/upload-artifact@v4
        with:
          name: dependency-audit
          path: audit-report.json

      - name: Check for vulnerabilities
        run: |
          if jq -e '.vulnerability_count > 0' audit-report.json; then
            echo "Vulnerabilities found!"
            exit 1
          fi

  verify-build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Verify build reproducibility
        run: python scripts/verify_build.py --clean

  lock-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Check lock file
        run: python scripts/lock_dependencies.py --check

      - name: Verify lock file
        run: python scripts/lock_dependencies.py --verify
```

### GitLab CI

Add to `.gitlab-ci.yml`:

```yaml
stages:
  - audit
  - verify

dependency-audit:
  stage: audit
  image: python:3.11
  before_script:
    - pip install pip-audit
  script:
    - python scripts/dependency_audit.py --json --output audit-report.json
  artifacts:
    paths:
      - audit-report.json
    reports:
      dependency_scanning: audit-report.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_BRANCH == "develop"

build-verification:
  stage: verify
  image: python:3.11
  script:
    - python scripts/verify_build.py --clean
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: dependency-audit
        name: Dependency Security Audit
        entry: python scripts/dependency_audit.py --skip-outdated
        language: system
        files: requirements.*\.txt$
        pass_filenames: false

      - id: lock-file-check
        name: Lock File Integrity Check
        entry: python scripts/lock_dependencies.py --check
        language: system
        files: requirements.*\.txt$
        pass_filenames: false
```

## Security Audit Process

### Regular Audits

1. **Weekly automated audits** (via CI/CD)
   - Run `dependency_audit.py` on schedule
   - Review and address findings within 7 days

2. **Pre-release audits**
   - Run full audit before any release
   - Verify all hashes are present
   - Check for new CVEs

3. **Post-incident audits**
   - Run audit after any security incident
   - Review all dependencies for compromise

### Handling Vulnerabilities

1. **Critical vulnerabilities (CVSS >= 9.0)**
   - Fix within 24 hours
   - Hotfix release if in production

2. **High vulnerabilities (CVSS 7.0-8.9)**
   - Fix within 7 days
   - Include in next release

3. **Medium vulnerabilities (CVSS 4.0-6.9)**
   - Fix within 30 days
   - Plan for next sprint

4. **Low vulnerabilities (CVSS < 4.0)**
   - Fix within 90 days
   - Include in regular updates

### Using pip-audit

Install pip-audit:
```bash
pip install pip-audit
```

Run audit:
```bash
# Audit current environment
pip-audit

# Audit requirements file
pip-audit --requirement backend/requirements-lock.txt

# Output as JSON
pip-audit --format json

# Fix vulnerabilities automatically
pip-audit --fix
```

## Troubleshooting

### Hash Mismatch Errors

If you see hash mismatch errors during installation:

```bash
# Regenerate lock file with fresh hashes
python scripts/lock_dependencies.py --with-hashes

# Or install without hash verification (development only)
pip install -r backend/requirements-lock.txt
```

### Dependency Conflicts

If `pip check` reports conflicts:

```bash
# Run verification to identify issues
python scripts/verify_build.py --no-venv

# Check specific package
pip show package-name

# Force reinstall
pip install --force-reinstall package-name==version
```

### Lock File Out of Date

If lock file doesn't match requirements.in:

```bash
# Regenerate lock file
python scripts/lock_dependencies.py

# Verify changes
python scripts/lock_dependencies.py --check
```

### pip-audit Not Found

Install pip-audit:
```bash
pip install pip-audit

# Or use without audit
python scripts/dependency_audit.py --skip-audit
```

## Best Practices

1. **Always use lock file for production**
   ```bash
   pip install -r backend/requirements-lock.txt
   ```

2. **Pin all direct dependencies**
   - Add to `requirements.in` with minimum version
   - Update `KNOWN_VERSIONS` in `lock_dependencies.py`

3. **Use hash verification in production**
   ```bash
   pip install --require-hashes -r backend/requirements-lock.txt
   ```

4. **Regular security audits**
   - Run `dependency_audit.py` weekly
   - Address vulnerabilities promptly

5. **Test before updating**
   - Run `verify_build.py` after changes
   - Test application functionality

6. **Document dependency changes**
   - Note why packages were added/removed
   - Track version changes in commit messages

## FAQ

**Q: Why use requirements.in + requirements-lock.txt instead of just requirements.txt?**

A: Separation of concerns:
- `requirements.in`: What we want (abstract requirements with ranges)
- `requirements-lock.txt`: What we get (exact pins with hashes)
- This allows easy updates while maintaining reproducibility

**Q: How do I add a development-only dependency?**

A: Create a separate `requirements-dev.in` and `requirements-dev-lock.txt`:
```bash
# requirements-dev.in
-r requirements.in
pytest>=7.0.0
black>=23.0.0
mypy>=1.0.0
```

**Q: Can I use pip-tools instead of this custom system?**

A: Yes! pip-tools (pip-compile) is excellent for this. Our system provides similar functionality with additional security features. To use pip-tools:
```bash
pip install pip-tools
pip-compile --generate-hashes requirements.in -o requirements-lock.txt
```

**Q: How do I handle optional dependencies?**

A: Use extras in requirements.in:
```bash
# requirements.in
package[extra1,extra2]>=1.0.0
```

**Q: What if a package doesn't have wheels?**

A: Hash verification works with both wheels and source distributions. The lock file will include hashes for all available distribution types.

## References

- [PEP 668 -- Marking Python base environments as "externally managed"](https://peps.python.org/pep-0668/)
- [pip documentation -- Hash-Checking Mode](https://pip.pypa.io/en/stable/topics/secure-installs/#hash-checking-mode)
- [pip-audit documentation](https://pypi.org/project/pip-audit/)
- [Python Packaging User Guide](https://packaging.python.org/)
