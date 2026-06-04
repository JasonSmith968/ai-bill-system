# Container Security

This document describes the security hardening measures applied to all Docker containers in the AI Accounting System, how to use them, and how to maintain them over time.

## Table of Contents

- [Security Measures Implemented](#security-measures-implemented)
- [Running the Security Scan](#running-the-security-scan)
- [Applying the Security Overlay](#applying-the-security-overlay)
- [What Each Hardening Measure Does](#what-each-hardening-measure-does)
- [CIS Docker Benchmark Alignment](#cis-docker-benchmark-alignment)
- [Maintaining Security Over Time](#maintaining-security-over-time)

---

## Security Measures Implemented

### Dockerfile-Level Hardening

All three Dockerfiles (`backend/Dockerfile`, `frontend/Dockerfile`, root `Dockerfile`) have been hardened with:

| Measure | Backend | Frontend | Root |
|---------|---------|----------|------|
| Non-root user | `appuser` | `nginx` | `appuser` |
| setuid/setgid removal | Yes | N/A (Alpine minimal) | Yes |
| Minimal base image | `python:3.12-slim` | `node:20-alpine` + `nginx:alpine` | `python:3.12-slim` |
| No-install-recommends | Yes | N/A | Yes |
| Layer cleanup | `rm -rf /var/lib/apt/lists/*` | N/A | `rm -rf /var/lib/apt/lists/*` |
| HEALTHCHECK | Yes | Yes | Yes |
| Proper file ownership | `chown -R appuser:appuser /app` | `chown -R nginx:nginx /usr/share/nginx/html` | `chown -R appuser:appuser /app` |

### docker-compose.security.yml Overlay

The security overlay adds runtime protections to every service:

- **no-new-privileges**: Prevents processes from gaining more privileges than their parent
- **cap-drop ALL**: Removes all Linux capabilities (adds back only what is strictly needed)
- **read-only**: Makes the root filesystem immutable at runtime
- **tmpfs mounts**: Provides writable ephemeral storage for runtime needs (logs, uploads, caches)

---

## Running the Security Scan

### Quick Scan

```bash
chmod +x scripts/docker_security_scan.sh
./scripts/docker_security_scan.sh
```

### Full Scan (with vulnerability scanning)

Requires [trivy](https://github.com/aquasecurity/trivy) or Docker Scout:

```bash
./scripts/docker_security_scan.sh --full
```

### Scan Output

The script produces:
- Console output with color-coded PASS/WARN/FAIL results
- A timestamped report file (`security-report-YYYYMMDD-HHMMSS.txt`)
- Exit code 1 if any FAIL conditions are found

### What the Scan Checks

1. **Container Runtime Security**: Root user, privileged mode, host network, capabilities, read-only filesystem, resource limits, PID limits, port bindings
2. **Docker Daemon Configuration**: Docker socket mounts, content trust
3. **Image Security**: HEALTHCHECK presence, default user
4. **Network Isolation**: Internal vs external networks
5. **Volume Mounts**: Sensitive host paths, .env files
6. **Image Vulnerabilities** (optional): CVEs in base image packages

---

## Applying the Security Overlay

The security overlay is designed to be layered on top of `docker-compose.prod.yml`:

```bash
# Start with security hardening
docker compose -f docker-compose.prod.yml -f docker-compose.security.yml up -d

# Or set it as an alias
export COMPOSE_FILE=docker-compose.prod.yml:docker-compose.security.yml
docker compose up -d
```

### Verifying Security Settings

After starting, verify the settings took effect:

```bash
# Check a container's security config
docker inspect ai-backend --format='
  Privileged: {{.HostConfig.Privileged}}
  ReadonlyRootfs: {{.HostConfig.ReadonlyRootfs}}
  SecurityOpt: {{.HostConfig.SecurityOpt}}
  CapDrop: {{.HostConfig.CapDrop}}
  User: {{.Config.User}}'

# Check running user
docker exec ai-backend whoami
# Expected: appuser
```

---

## What Each Hardening Measure Does

### Non-Root User (`USER appuser`)

**Why**: Running as root inside a container means that if an attacker escapes the container, they have root on the host. A non-root user limits the blast radius of any compromise.

**CIS Reference**: 4.1 - Ensure that a user for the container has been created

### Removing setuid/setgid Binaries

**Why**: setuid/setgid binaries allow privilege escalation. Even with `no-new-privileges`, removing these binaries eliminates the attack vector entirely.

**How**: `find / -perm /6000 -type f -exec chmod a-s {} +`

**CIS Reference**: 4.1 - Ensure that a user for the container has been created

### `no-new-privileges`

**Why**: Prevents processes from using setuid/setgid binaries or other mechanisms to gain elevated privileges. This is a kernel-level enforcement that works even if the container is compromised.

**CIS Reference**: 5.25 - Ensure that the container is restricted from acquiring additional privileges

### `cap-drop ALL`

**Why**: Linux capabilities split root privileges into discrete units (e.g., `NET_BIND_SERVICE`, `CHOWN`). Dropping all capabilities and adding back only what is needed follows the principle of least privilege.

**Common capabilities needed**:
- `NET_BIND_SERVICE`: Binding to ports below 1024 (nginx)
- `CHOWN`, `SETGID`, `SETUID`: MySQL initialization
- `DAC_OVERRIDE`: MySQL data directory access

**CIS Reference**: 5.3 - Ensure Linux kernel capabilities are restricted

### Read-Only Root Filesystem

**Why**: Prevents attackers from modifying binaries, planting backdoors, or writing malicious scripts inside the container. Any writes must go to explicitly declared tmpfs or volume mounts.

**CIS Reference**: 5.12 - Ensure that the container's root filesystem is mounted as read-only

### tmpfs Mounts

**Why**: Provides writable ephemeral storage for runtime needs (logs, uploads, caches) while keeping the rest of the filesystem read-only. tmpfs is memory-backed and does not persist across container restarts.

### Resource Limits (Memory/CPU/PID)

**Why**: Prevents denial-of-service attacks where a compromised container consumes all host resources. PID limits prevent fork bombs.

**CIS Reference**: 5.10 - Ensure that the memory usage for container is limited, 5.11 - Ensure that CPU priority is set appropriately

### Network Isolation

**Why**: The `backend-net` is marked `internal: true`, meaning containers on that network cannot reach the internet. Only `frontend-net` has external access. This limits data exfiltration paths.

---

## CIS Docker Benchmark Alignment

This project addresses the following CIS Docker Benchmark v1.6.0 controls:

| CIS Control | Description | Status |
|-------------|-------------|--------|
| 2.1 | Restrict network traffic between containers | Implemented (internal networks) |
| 2.4 | Do not use privileged containers | Implemented (cap-drop ALL) |
| 4.1 | Ensure a user for the container has been created | Implemented (appuser/nginx) |
| 4.2 | Use trusted base images to build your images | Partial (pin digests for full compliance) |
| 4.3 | Do not install unnecessary packages | Implemented (no-install-recommends) |
| 4.6 | Add HEALTHCHECK instruction | Implemented |
| 4.7 | Do not use update instructions alone | Implemented (apt-get update && install in one RUN) |
| 4.9 | Use COPY instead of ADD | Implemented |
| 4.10 | Do not store secrets in Dockerfiles | Implemented (env_file in compose) |
| 5.2 | Do not use privileged containers | Implemented |
| 5.3 | Restrict Linux kernel capabilities | Implemented (cap-drop ALL, selective cap-add) |
| 5.9 | Do not share the host's network namespace | Implemented (bridge networks) |
| 5.10 | Limit container memory | Implemented (deploy.resources.limits) |
| 5.12 | Mount container's root filesystem as read-only | Implemented (read_only + tmpfs) |
| 5.25 | Restrict container from acquiring additional privileges | Implemented (no-new-privileges) |

---

## Maintaining Security Over Time

### Regular Tasks

1. **Run the security scan weekly**:
   ```bash
   ./scripts/docker_security_scan.sh --full
   ```

2. **Update base images monthly**:
   ```bash
   docker compose -f docker-compose.prod.yml build --no-cache
   ```

3. **Review and rotate secrets quarterly**:
   - Database passwords
   - Redis password
   - API keys
   - SSL certificates

### Pinning Image Digests

For full reproducibility, pin base images by SHA256 digest:

```bash
# Get the digest
docker pull python:3.12-slim
docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim

# Use in Dockerfile
FROM python:3.12-slim@sha256:abc123...
```

Update digests monthly or when security patches are released.

### CI/CD Integration

Add the security scan to your CI pipeline:

```yaml
# GitHub Actions example
- name: Security scan
  run: |
    chmod +x scripts/docker_security_scan.sh
    ./scripts/docker_security_scan.sh --full
```

### Incident Response

If a container is compromised:

1. Stop all containers: `docker compose -f docker-compose.prod.yml down`
2. Preserve evidence: `docker commit <container> evidence-<name>-<timestamp>`
3. Review logs: `docker logs <container> > container-logs.txt`
4. Rotate all credentials
5. Rebuild from scratch with `--no-cache`
6. Run the security scan before restarting

### Monitoring for Drift

Check for configuration drift:

```bash
# Compare running config vs expected
docker inspect ai-backend --format='{{json .HostConfig.SecurityOpt}}' | jq .
docker inspect ai-backend --format='{{json .HostConfig.CapDrop}}' | jq .
docker inspect ai-backend --format='{{json .HostConfig.ReadonlyRootfs}}' | jq .
```
