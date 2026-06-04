#!/usr/bin/env bash
# ==============================================================================
# AI Accounting System — Server Hardening Script
# ==============================================================================
# Targets: Ubuntu 24.04 LTS
# Hardens: SSH, UFW, fail2ban, Docker daemon, kernel parameters
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

DRY_RUN=false
SSH_PORT="${SSH_PORT:-22}"
ADMIN_IP="${ADMIN_IP:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> /var/log/server-hardening.log; }
info() { echo -e "${GREEN}[INFO]${NC} $*"; log "INFO: $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; log "WARN: $*"; }
fatal() { echo -e "${RED}[FATAL]${NC} $*"; log "FATAL: $*"; exit 1; }

run_cmd() {
    if $DRY_RUN; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $*"
        return 0
    fi
    "$@"
}

# ==============================================================================
# Parse Arguments
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --ssh-port)   SSH_PORT="$2"; shift 2 ;;
        --admin-ip)   ADMIN_IP="$2"; shift 2 ;;
        --dry-run)    DRY_RUN=true; shift ;;
        -h|--help)
            echo "Usage: $(basename "$0") [--ssh-port PORT] [--admin-ip IP] [--dry-run]"
            exit 0
            ;;
        *) fatal "Unknown option: $1" ;;
    esac
done

# ==============================================================================
# Check Root
# ==============================================================================

if [ "$(id -u)" -ne 0 ]; then
    fatal "This script must be run as root (sudo ./deploy/harden.sh)"
fi

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════╗"
echo "║   Server Hardening — Ubuntu 24.04 LTS       ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ==============================================================================
# 1. System Update
# ==============================================================================

echo -e "\n${CYAN}━━━ 1. System Update ━━━${NC}"
info "Updating system packages..."
run_cmd apt-get update -qq
run_cmd apt-get upgrade -y -qq
info "System updated"

# ==============================================================================
# 2. SSH Hardening
# ==============================================================================

echo -e "\n${CYAN}━━━ 2. SSH Hardening ━━━${NC}"

SSHD_CONFIG="/etc/ssh/sshd_config"
SSHD_BACKUP="/etc/ssh/sshd_config.backup.$(date +%Y%m%d)"

if [ -f "$SSHD_CONFIG" ]; then
    run_cmd cp "$SSHD_CONFIG" "$SSHD_BACKUP"
    info "Backed up sshd_config to $SSHD_BACKUP"
fi

# Create hardened SSH config drop-in
cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'SSHEOF'
# AI Accounting System — SSH Hardening
# Applied by deploy/harden.sh

# Protocol & Authentication
Protocol 2
PermitRootLogin prohibit-password
PasswordAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM yes

# Key-based only
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

# Security
MaxAuthTries 3
MaxSessions 5
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2

# Disable unused features
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
GatewayPorts no

# Logging
LogLevel VERBOSE

# Restrict to strong ciphers and MACs
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org

# Banner
Banner /etc/ssh/banner
SSHEOF

# Create SSH banner
cat > /etc/ssh/banner <<'BANNEREOF'
*******************************************************************
*  WARNING: Authorized access only. All activity is monitored.    *
*  Unauthorized access will be prosecuted to the full extent of   *
*  applicable law.                                                *
*******************************************************************
BANNEREOF

# Set custom SSH port if different from 22
if [ "$SSH_PORT" != "22" ]; then
    sed -i "s/^#\?Port .*/Port $SSH_PORT/" "$SSHD_CONFIG"
    info "SSH port changed to $SSH_PORT"
fi

info "SSH hardened"
warn "Ensure your SSH public key is in ~/.ssh/authorized_keys before restarting sshd!"

# ==============================================================================
# 3. UFW Firewall
# ==============================================================================

echo -e "\n${CYAN}━━━ 3. UFW Firewall ━━━${NC}"

# Install UFW if not present
if ! command -v ufw &> /dev/null; then
    run_cmd apt-get install -y -qq ufw
fi

# Reset to defaults
run_cmd ufw --force reset

# Default policies
run_cmd ufw default deny incoming
run_cmd ufw default allow outgoing

# SSH (rate limited)
run_cmd ufw limit "$SSH_PORT/tcp" comment 'SSH rate-limited'

# HTTP/HTTPS
run_cmd ufw allow 80/tcp comment 'HTTP'
run_cmd ufw allow 443/tcp comment 'HTTPS'

# Monitoring (localhost only — these are bound to 127.0.0.1 in docker-compose)
# No additional rules needed since ports are bound to 127.0.0.1

# Admin IP whitelist (if specified)
if [ -n "$ADMIN_IP" ]; then
    run_cmd ufw allow from "$ADMIN_IP" to any port 9090 comment 'Prometheus admin'
    run_cmd ufw allow from "$ADMIN_IP" to any port 3000 comment 'Grafana admin'
    run_cmd ufw allow from "$ADMIN_IP" to any port 5601 comment 'Kibana admin'
    info "Admin access granted to $ADMIN_IP"
fi

# Enable UFW
run_cmd ufw --force enable
info "UFW firewall enabled"

# Show status
ufw status verbose 2>/dev/null || true

# ==============================================================================
# 4. fail2ban
# ==============================================================================

echo -e "\n${CYAN}━━━ 4. fail2ban ━━━${NC}"

# Install fail2ban
if ! command -v fail2ban-server &> /dev/null; then
    run_cmd apt-get install -y -qq fail2ban
fi

# Create local configuration
cat > /etc/fail2ban/jail.local <<F2BEOF
# AI Accounting System — fail2ban configuration
# Applied by deploy/harden.sh

[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
banaction = ufw
backend = systemd

[sshd]
enabled = true
port = $SSH_PORT
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 7200

[nginx-http-auth]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 5

[nginx-botsearch]
enabled = true
port = http,https
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-req-limit]
enabled = true
port = http,https
filter = nginx-req-limit
logpath = /var/log/nginx/error.log
maxretry = 10
bantime = 7200

# Recidive jail — ban repeat offenders longer
[recidive]
enabled = true
filter = recidive
logpath = /var/log/fail2ban.log
action = ufw[name=recidive, port="0:65535"]
bantime = 604800
findtime = 86400
maxretry = 3
F2BEOF

# Restart fail2ban
run_cmd systemctl enable fail2ban
run_cmd systemctl restart fail2ban
info "fail2ban configured and started"

# ==============================================================================
# 5. Docker Daemon Security
# ==============================================================================

echo -e "\n${CYAN}━━━ 5. Docker Daemon Security ━━━${NC}"

# Create Docker daemon configuration
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'DOCKEREOF'
{
    "live-restore": true,
    "userland-proxy": false,
    "no-new-privileges": true,
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "20m",
        "max-file": "5"
    },
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 65536,
            "Soft": 65536
        }
    },
    "storage-driver": "overlay2",
    "icc": false
}
DOCKEREOF

run_cmd systemctl restart docker
info "Docker daemon hardened"

# Restrict docker.sock access
if [ -S /var/run/docker.sock ]; then
    chmod 660 /var/run/docker.sock
    info "docker.sock permissions tightened"
fi

# ==============================================================================
# 6. Kernel Hardening (sysctl)
# ==============================================================================

echo -e "\n${CYAN}━━━ 6. Kernel Hardening ━━━${NC}"

cat > /etc/sysctl.d/99-ai-accounting.conf <<'SYSCTLEOF'
# AI Accounting System — Kernel Parameters
# Applied by deploy/harden.sh

# Network security
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# IPv6 — disable if not needed
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Memory
vm.swappiness = 10
vm.overcommit_memory = 1

# File descriptors
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288

# Connection tracking
net.netfilter.nf_conntrack_max = 131072
SYSCTLEOF

run_cmd sysctl --system > /dev/null 2>&1
info "Kernel parameters hardened"

# ==============================================================================
# 7. Automatic Security Updates
# ==============================================================================

echo -e "\n${CYAN}━━━ 7. Automatic Security Updates ━━━${NC}"

run_cmd apt-get install -y -qq unattended-upgrades

cat > /etc/apt/apt.conf.d/50unattended-upgrades <<'UUEOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
UUEOF

run_cmd dpkg-reconfigure -plow unattended-upgrades 2>/dev/null || true
info "Automatic security updates enabled"

# ==============================================================================
# 8. Additional Security Packages
# ==============================================================================

echo -e "\n${CYAN}━━━ 8. Additional Security Packages ━━━${NC}"

# Install security tools
PACKAGES=(
    "auditd"
    "rkhunter"
    "logwatch"
    "needrestart"
)

for pkg in "${PACKAGES[@]}"; do
    if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        run_cmd apt-get install -y -qq "$pkg" 2>/dev/null || warn "Failed to install $pkg"
    fi
done

# Configure auditd
if command -v auditctl &> /dev/null; then
    cat >> /etc/audit/rules.d/ai-accounting.rules <<'AUDITEOF'
# Monitor Docker socket
-w /var/run/docker.sock -p rwxa -k docker

# Monitor SSH config
-w /etc/ssh/sshd_config -p wa -k sshd_config
-w /etc/ssh/sshd_config.d/ -p wa -k sshd_config

# Monitor user/group changes
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity

# Monitor sudo usage
-w /etc/sudoers -p wa -k sudoers
AUDITEOF
    run_cmd systemctl restart auditd 2>/dev/null || true
    info "Auditd rules configured"
fi

info "Security packages installed"

# ==============================================================================
# Summary
# ==============================================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           HARDENING COMPLETE                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Hardened components:"
echo "  [x] SSH — key-only auth, strong ciphers, rate limiting"
echo "  [x] UFW — deny-all incoming, allow 80/443/$SSH_PORT"
echo "  [x] fail2ban — SSH/nginx jails, recidive escalation"
echo "  [x] Docker — no-new-privileges, ICC disabled, log limits"
echo "  [x] Kernel — SYN cookies, ICMP hardening, low swappiness"
echo "  [x] Auto-updates — unattended security patches"
echo "  [x] Auditd — Docker/SSH/sudo monitoring"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "  1. Ensure your SSH key is in ~/.ssh/authorized_keys"
echo "  2. Test SSH connection in another terminal BEFORE disconnecting"
echo "  3. Review UFW rules: sudo ufw status verbose"
echo "  4. Check fail2ban: sudo fail2ban-client status"
echo ""
echo "Log: /var/log/server-hardening.log"
