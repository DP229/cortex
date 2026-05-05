#!/bin/bash
# =============================================================================
# Cortex Deployment Scripts — neuronmesh.dev
# =============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/DP229/cortex/master/scripts/deploy.sh | bash
#
# Or clone and run locally:
#   git clone https://github.com/DP229/cortex.git
#   cd cortex/scripts
#   chmod +x *.sh
#   ./01-setup-vps.sh        # Run as root on fresh VPS
#   ./02-install-app.sh       # Run as root
#   ./03-install-ollama.sh    # Run as root
#   ./04-setup-caddy.sh       # Run as root
#   ./05-setup-github-runner.sh  # Run as cortex user
#   ./06-backup.sh            # Run as cortex user (add to crontab)
# =============================================================================

set -euo pipefail

# Color codes
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
NC='\033[0m' # No Color

DOMAIN="${DOMAIN:-neuronmesh.dev}"
APP_SUBDOMAIN="${APP_SUBDOMAIN:-app.neuronmesh.dev}"
OLLAMA_SUBDOMAIN="${OLLAMA_SUBDOMAIN:-ollama.neuronmesh.dev}"
APP_USER="${APP_USER:-cortex}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
INSTALL_DIR="/opt/cortex"
LOG_DIR="/var/log/cortex"
BACKUP_DIR="/var/backups/cortex"
EVIDENCE_DIR="/var/lib/cortex/evidence"

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

need_root() {
  if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root. Hint: sudo ./$(basename $0)"
  fi
}

need_user() {
  if [[ $EUID -eq 0 ]]; then
    error "This script must be run as the '$APP_USER' user (not root)."
  fi
}

# ---------------------------------------------------------------------------
# 01 — Initial VPS setup (run as root on fresh Ubuntu 22.04)
# ---------------------------------------------------------------------------
setup_vps() {
  need_root
  info "=== Step 1/6: Initial VPS setup ==="

  export DEBIAN_FRONTEND=noninteractive

  # System update
  apt update && apt upgrade -y

  # Essential packages
  apt install -y curl wget git ufw fail2ban python3.10 python3.10-venv python3-pip \
    certbot dnsutils unzip vat

  # Create cortex user
  if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash -G sudo "$APP_USER"
    ok "Created user: $APP_USER"
  else
    info "User $APP_USER already exists"
  fi

  # Sudoers: passwordless for cortex user
  mkdir -p /etc/sudoers.d/
  echo "$APP_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/$APP_USER
  chmod 0440 /etc/sudoers.d/$APP_USER
  ok "Passwordless sudo for $APP_USER"

  # Firewall — allow SSH, HTTP, HTTPS only
  ufw --force reset
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow ssh
  ufw allow http
  ufw allow https
  ufw --force enable
  ok "Firewall enabled (SSH, HTTP, HTTPS)"

  # Fail2Ban (SSH protection)
  cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
EOF
  systemctl enable fail2ban
  systemctl restart fail2ban
  ok "Fail2Ban configured"

  # Create required directories
  mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$BACKUP_DIR" "$EVIDENCE_DIR"
  chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR" "$LOG_DIR" "$BACKUP_DIR" "$EVIDENCE_DIR"
  chmod 0755 "$INSTALL_DIR" "$LOG_DIR" "$BACKUP_DIR" "$EVIDENCE_DIR"
  ok "Directories created"

  # Clone repository
  if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    sudo -u "$APP_USER" git clone https://github.com/DP229/cortex.git "$INSTALL_DIR"
    ok "Repository cloned to $INSTALL_DIR"
  else
    info "Repository already exists at $INSTALL_DIR"
    sudo -u "$APP_USER" git -C "$INSTALL_DIR" pull origin master
  fi

  # Python venv
  if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    sudo -u "$APP_USER" python3.10 -m venv "$INSTALL_DIR/.venv"
    ok "Python venv created"
  fi
  sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
  sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR"
  ok "Python packages installed"

  # .env file
  if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cat > "$INSTALL_DIR/.env" <<EOF
# ============================================================
# Cortex — neuronmesh.dev
# ============================================================
DEBUG=false
CORS_ORIGINS=https://$APP_SUBDOMAIN
ALLOWED_HOSTS=$APP_SUBDOMAIN

# Security (generate new keys!)
ENCRYPTION_KEY=<run: openssl rand -base64 32>
JWT_SECRET=<run: openssl rand -base64 32>

# Database (SQLite — swap for postgresql:// in production)
DATABASE_URL=sqlite:///./cortex.db

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=$OLLAMA_MODEL

# Evidence Storage (T2 qualification artifacts)
EVIDENCE_DIR=$EVIDENCE_DIR

# Logging
LOG_LEVEL=INFO
LOG_FILE=$LOG_DIR/app.log
EOF
    chmod 0600 "$INSTALL_DIR/.env"
    chown "$APP_USER:$APP_USER" "$INSTALL_DIR/.env"
    warn ".env created at $INSTALL_DIR/.env — EDIT IT and add real ENCRYPTION_KEY and JWT_SECRET!"
  else
    info ".env already exists"
  fi

  ok "=== Step 1/6 complete ==="
  echo ""
  info "NEXT: Run as root: ./02-install-app.sh"
  info "       Then:     ./03-install-ollama.sh"
}

# ---------------------------------------------------------------------------
# 02 — Application install / update (run as root after setup-vps)
# ---------------------------------------------------------------------------
install_app() {
  need_root
  info "=== Step 2/6: Application install ==="

  cd "$INSTALL_DIR"

  # Update from git
  sudo -u "$APP_USER" git pull origin master

  # Ensure all new dependencies are installed
  sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install -e . --quiet

  # Generate keys if not set
  if grep -q '<run:' "$INSTALL_DIR/.env"; then
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 32)
    sed -i "s|<run: openssl rand -base64 32>|$ENCRYPTION_KEY|" "$INSTALL_DIR/.env"
    sed -i "s|<run: openssl rand -base64 32>|$JWT_SECRET|" "$INSTALL_DIR/.env"
    ok "Generated ENCRYPTION_KEY and JWT_SECRET"
  fi

  # Test API starts
  sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/python" -c "from cortex.api import app; print('API import OK')"
  ok "API import verified"

  # Systemd service
  cat > /etc/systemd/system/cortex.service <<EOF
[Unit]
Description=Cortex — EN 50128 Railway Safety Platform
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/.venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn cortex.api:app --host 127.0.0.1 --port 8080 --workers 2
Restart=always
RestartSec=10
StandardOut=append:$LOG_DIR/app.log
StandardError=append:$LOG_DIR/app.log

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable cortex
  systemctl restart cortex

  # Wait for API to come up
  sleep 5
  if curl -sf http://localhost:8080/health > /dev/null; then
    ok "Cortex API is running on port 8080"
  else
    warn "Cortex API not responding yet — check: journalctl -u cortex -f"
  fi

  ok "=== Step 2/6 complete ==="
}

# ---------------------------------------------------------------------------
# 03 — Ollama + model install (run as root)
# ---------------------------------------------------------------------------
install_ollama() {
  need_root
  info "=== Step 3/6: Ollama install ($OLLAMA_MODEL) ==="

  # Install Ollama
  if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama installed"
  else
    info "Ollama already installed: $(ollama --version)"
  fi

  # Configure Ollama to listen locally (Cloudflare handles network)
  OLLAMA_HOST_LINE="OLLAMA_HOST=127.0.0.1"
  ENV_FILE="/etc/systemd/system/ollama.service.d/override.conf"
  mkdir -p "$(dirname $ENV_FILE)"
  cat > "$ENV_FILE" <<EOF
[Service]
Environment=OLLAMA_HOST=127.0.0.1
Environment=OLLAMA_MODELS=/var/lib/ollama
EOF

  # Set models directory
  mkdir -p /var/lib/ollama
  systemctl daemon-reload
  systemctl restart ollama

  # Pull model (llama3.2:3b — ~2GB, fast for system engineering tasks)
  if sudo -u "$APP_USER" ollama list | grep -q "$OLLAMA_MODEL"; then
    info "Model $OLLAMA_MODEL already present"
  else
    info "Pulling model $OLLAMA_MODEL (~2GB, may take several minutes)..."
    sudo -u "$APP_USER" ollama pull "$OLLAMA_MODEL"
    ok "Model $OLLAMA_MODEL pulled"
  fi

  # Test model
  sudo -u "$APP_USER" timeout 30 ollama run "$OLLAMA_MODEL" "Say 'OK' if you can hear me." 2>/dev/null | head -1 || true
  ok "Ollama model verified"

  ok "=== Step 3/6 complete ==="
}

# ---------------------------------------------------------------------------
# 04 — Caddy reverse proxy (run as root)
# ---------------------------------------------------------------------------
setup_caddy() {
  need_root
  info "=== Step 4/6: Caddy reverse proxy ==="

  # Install Caddy
  if ! command -v caddy &>/dev/null; then
    apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee -a /etc/apt/sources.list.d/caddy-stable.list
    apt update && apt install -y caddy
    ok "Caddy installed"
  else
    info "Caddy already installed: $(caddy version)"
  fi

  # Stop Caddy before editing config
  systemctl stop caddy

  # Caddyfile
  cat > /etc/caddy/Caddyfile <<EOF
# ============================================================
# Cortex on neuronmesh.dev
# Cloudflare provides SSL (full strict mode)
# This Caddy listens on HTTP only — Cloudflare proxies HTTPS
# ============================================================

# Main app — Cortex FastAPI backend
$APP_SUBDOMAIN {
    reverse_proxy localhost:8080
    log {
        output file $LOG_DIR/caddy-$APP_SUBDOMAIN.log
    }
}

# Ollama API (restricted to internal use)
$OLLAMA_SUBDOMAIN {
    reverse_proxy localhost:11434
    log {
        output file $LOG_DIR/caddy-$OLLAMA_SUBDOMAIN.log
    }
}

# Root redirect to app subdomain
$DOMAIN {
    redir https://$APP_SUBDOMAIN{uri}
}
EOF

  # Set correct permissions
  chown root:root /etc/caddy/Caddyfile
  chmod 0644 /etc/caddy/Caddyfile

  # Validate config
  caddy validate --config /etc/caddy/Caddyfile

  systemctl enable caddy
  systemctl restart caddy
  sleep 3

  if systemctl is-active --quiet caddy; then
    ok "Caddy is running"
  else
    error "Caddy failed to start — check: journalctl -u caddy -f"
  fi

  ok "=== Step 4/6 complete ==="
  echo ""
  info "NEXT: Point Cloudflare DNS at this VPS:"
  info "  Type   Name    Content (VPS IP)"
  info "  A      app     <YOUR_VPS_IP>"
  info "  A      ollama  <YOUR_VPS_IP>"
  info "  Then run: ./05-setup-github-runner.sh"
}

# ---------------------------------------------------------------------------
# 05 — GitHub Actions self-hosted runner (run as cortex user)
# ---------------------------------------------------------------------------
setup_github_runner() {
  need_user
  info "=== Step 5/6: GitHub Actions self-hosted runner ==="

  REPO_URL="https://github.com/DP229/cortex"
  RUNNER_DIR="$HOME/actions-runner"

  # Check if runner already exists
  if [[ -d "$RUNNER_DIR" && -d "$RUNNER_DIR/.runner" ]]; then
    warn "Runner already configured at $RUNNER_DIR"
    info "To reconfigure: rm -rf $RUNNER_DIR && ./05-setup-github-runner.sh"
    return 0
  fi

  # Check for GitHub PAT
  if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    error "GITHUB_TOKEN not set.

  Create a GitHub Personal Access Token (PAT):
    https://github.com/settings/tokens → Fine-grained → Repo: All

  Then run:
    export GITHUB_TOKEN=ghp_your_token_here
    ./05-setup-github-runner.sh
"
  fi

  # Get latest runner version
  info "Downloading GitHub Actions runner..."
  RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
  ARCH=$(uname -m)
  case $ARCH in
    x86_64) ARCH_DIR="x64" ;;
    aarch64) ARCH_DIR="arm64" ;;
    *) error "Unsupported arch: $ARCH" ;;
  esac

  mkdir -p "$RUNNER_DIR"
  cd "$RUNNER_DIR"

  curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${ARCH_DIR}-${RUNNER_VERSION}.tar.gz" \
    -o runner.tar.gz

  sudo -u "$APP_USER" tar xzf runner.tar.gz
  rm runner.tar.gz
  ok "Runner downloaded and extracted"

  # Configure runner
  info "Running runner configuration (interactive)..."
  echo ""
  warn "If the next step asks for a URL and token, use:"
  warn "  Repository: $REPO_URL"
  warn "  Token: Get from https://github.com/DP229/cortex → Settings → Actions → Runners"
  echo ""

  ./config.sh --url "$REPO_URL" --token "$GITHUB_TOKEN" \
    --name "neuronmesh-runner" \
    --work "_work" \
    --labels "self-hosted,railway-safety" \
    --unattended \
    --replace

  # Systemd service for runner
  sudo systemctl enable actions.runner.cortex.service
  sudo systemctl start actions.runner.cortex.service

  sleep 3
  if systemctl is-active --quiet actions.runner.cortex.service; then
    ok "GitHub runner is running"
  else
    warn "Runner service not active yet — check: journalctl -u actions.runner.cortex.service -f"
  fi

  ok "=== Step 5/6 complete ==="
  echo ""
  info "Runner registered at: https://github.com/DP229/cortex → Settings → Actions → Runners"
}

# ---------------------------------------------------------------------------
# 06 — Backup script (run as cortex user, add to crontab)
# ---------------------------------------------------------------------------
setup_backup() {
  need_user
  info "=== Step 6/6: Backup setup ==="

  BACKUP_SCRIPT="$HOME/backup.sh"

  cat > "$BACKUP_SCRIPT" <<EOF
#!/bin/bash
# Cortex Backup Script — EN 50128 Evidence Retention
# Add to crontab: 0 2 * * * /home/cortex/backup.sh

set -euo pipefail

DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_DIR"
DB_PATH="$INSTALL_DIR/cortex.db"
EVIDENCE_DIR="$EVIDENCE_DIR"

mkdir -p "\$BACKUP_DIR"

# Backup database
if [[ -f "\$DB_PATH" ]]; then
  cp "\$DB_PATH" "\$BACKUP_DIR/cortex_\${DATE}.db"
fi

# Backup evidence artifacts
if [[ -d "\$EVIDENCE_DIR" ]]; then
  tar -czf "\$BACKUP_DIR/evidence_\${DATE}.tar.gz" -C /var/lib/cortex evidence
fi

# Backup .env and .cortex
tar -czf "\$BACKUP_DIR/config_\${DATE}.tar.gz" \\
  "$INSTALL_DIR/.env" \\
  "$INSTALL_DIR/.cortex" 2>/dev/null || true

# Prune old backups (keep 90 days locally — EN 50128 long-term retention is in your backup system)
find "\$BACKUP_DIR" -type f -mtime +90 -delete 2>/dev/null || true

echo "\$(date) - Backup completed: \$DATE" >> "$LOG_DIR/backup.log"
EOF

  chmod +x "$BACKUP_SCRIPT"

  # Add to crontab if not already present
  CRON_ENTRY="0 2 * * * $HOME/backup.sh >> $LOG_DIR/backup.log 2>&1"
  if crontab -l 2>/dev/null | grep -q "$HOME/backup.sh"; then
    info "Backup cron already configured"
  else
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    ok "Backup cron added (daily at 02:00)"
  fi

  ok "=== Step 6/6 complete ==="
  echo ""
  info "Backup script: $BACKUP_SCRIPT"
  info "Logs: $LOG_DIR/backup.log"
  info "Backups: $BACKUP_DIR"
}

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------
main() {
  if [[ $# -eq 0 ]]; then
    cat <<'HELP'
Usage: ./deploy.sh <stage>

Stages:
  1  — Initial VPS setup (run as root, Ubuntu 22.04 fresh)
  2  — Install/update Cortex application (run as root)
  3  — Install Ollama + model (run as root)
  4  — Configure Caddy reverse proxy (run as root)
  5  — GitHub Actions self-hosted runner (run as cortex user)
  6  — Backup script setup (run as cortex user)

All stages:
  ./deploy.sh 1 2 3 4 5 6

Or run individually:
  sudo ./deploy.sh 1
  sudo ./deploy.sh 2
  sudo ./deploy.sh 3
  sudo ./deploy.sh 4
  # Switch to cortex user:
  ./deploy.sh 5
  ./deploy.sh 6

Environment variables (override before running):
  DOMAIN=neuronmesh.dev
  APP_SUBDOMAIN=app.neuronmesh.dev
  OLLAMA_SUBDOMAIN=ollama.neuronmesh.dev
  APP_USER=cortex
  OLLAMA_MODEL=llama3.2:3b
HELP
    exit 0
  fi

  for stage in "$@"; do
    case $stage in
      1) setup_vps ;;
      2) install_app ;;
      3) install_ollama ;;
      4) setup_caddy ;;
      5) setup_github_runner ;;
      6) setup_backup ;;
      *) error "Unknown stage: $stage" ;;
    esac
  done

  echo ""
  ok "All done! 🎉"
}

main "$@"
