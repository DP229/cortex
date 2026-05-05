# Cortex Deployment Guide

Production deployment guide for Cortex — EN 50128 Railway Safety Compliance Platform.

## Prerequisites

### System Requirements
- **OS:** Linux (Ubuntu 20.04+ recommended)
- **Python:** 3.10+
- **RAM:** 8GB minimum (16GB recommended for T2 qualification workloads)
- **Storage:** 20GB minimum for database, evidence artifacts, and logs

### Required Software
- Python 3.10+
- pip
- nginx (for production reverse proxy)
- SSL certificate
- Redis (optional, for distributed rate limiting)

## Environment Setup

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and utilities
sudo apt install python3.10 python3.10-venv python3-pip curl -y

# Install nginx and certbot
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 2. Set Up Application Directory

```bash
# Create application directory
sudo mkdir -p /opt/cortex
sudo chown $USER:$USER /opt/cortex
cd /opt/cortex

# Clone repository
git clone https://github.com/DP229/cortex.git .

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Install additional production dependencies
pip install gunicorn uvicorn[standard]
```

### 3. Environment Variables

Create `.env` file at `/opt/cortex/.env`:

```bash
# Application
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com

# Security
ENCRYPTION_KEY=<generate-with-openssl-rand-base64-32>
JWT_SECRET=<generate-with-openssl-rand-base64-32>

# Database (SQLite default — for production use PostgreSQL)
DATABASE_URL=sqlite:///./cortex.db

# Ollama (local AI — no external data transmission)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Rate Limiting (optional — requires Redis)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/cortex/app.log

# Evidence Storage (T2 qualification artifacts)
EVIDENCE_DIR=/var/lib/cortex/evidence
```

Generate secure keys:

```bash
# Generate encryption key
openssl rand -base64 32

# Generate JWT secret
openssl rand -base64 32
```

### 4. Create Required Directories

```bash
# Create evidence directory (T2 qualification artifacts)
sudo mkdir -p /var/lib/cortex/evidence
sudo chown $USER:$USER /var/lib/cortex/evidence

# Create log directory
sudo mkdir -p /var/log/cortex
sudo chown $USER:$USER /var/log/cortex
```

### 5. Initialize Database

```bash
cd /opt/cortex
source venv/bin/activate

# Database tables are auto-created on first API startup
# Verify by checking the API health endpoint after starting
curl http://localhost:8080/health
```

### 6. Configure Systemd Service

Create `/etc/systemd/system/cortex.service`:

```ini
[Unit]
Description=Cortex — EN 50128 Railway Safety Compliance Platform
After=network.target

[Service]
Type=notify
User=cortex
Group=cortex
WorkingDirectory=/opt/cortex
Environment="PATH=/opt/cortex/venv/bin"
ExecStart=/opt/cortex/venv/bin/uvicorn cortex.api:app --host 127.0.0.1 --port 8080 --workers 4
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create the cortex user:

```bash
sudo useradd -r -s /bin/false cortex
sudo chown -R cortex:cortex /opt/cortex
sudo chown -R cortex:cortex /var/lib/cortex
sudo chown -R cortex:cortex /var/log/cortex
```

Enable and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cortex
sudo systemctl start cortex
sudo systemctl status cortex
```

### 7. Configure Nginx

Create `/etc/nginx/sites-available/cortex`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

    # Proxy to application
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        limit_req zone=api burst=200 nodelay;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:8080/health;
        proxy_set_header Host $host;
        limit_req zone=api burst=50 nodelay;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/cortex /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8. SSL Certificate

```bash
# Obtain Let's Encrypt certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal (certbot auto-configures this)
sudo certbot renew --dry-run
```

### 9. T2 Qualification CI/CD Setup

Add to your GitHub Actions workflow (`.github/workflows/ci.yaml`):

```yaml
- name: T2 Qualification
  run: |
    python -m cortex.ci_qualify qualify --sil-target SIL2

- name: Regression Guard
  run: |
    python -m cortex.regression_guard verify
```

Evidence artifacts are stored in `.cortex/evidence/` and `.cortex/ci_evidence.json`.

### 10. Monitoring Setup

Prometheus metrics endpoint at `GET /metrics`:

```yaml
# /etc/prometheus/prometheus.yml
- job_name: 'cortex'
  static_configs:
    - targets: ['localhost:8080']
  scrape_interval: 30s
  metrics_path: /metrics
```

### 11. Backup Configuration

Create `/opt/cortex/scripts/backup.sh`:

```bash
#!/bin/bash
# Cortex Backup Script — Railway Safety Evidence

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/cortex"
DB_PATH="/opt/cortex/cortex.db"
EVIDENCE_DIR="/var/lib/cortex/evidence"

mkdir -p $BACKUP_DIR

# Backup database
cp $DB_PATH $BACKUP_DIR/cortex_$DATE.db

# Backup evidence artifacts
tar -czf $BACKUP_DIR/evidence_$DATE.tar.gz -C /var/lib/cortex evidence

# Backup environment config
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/cortex/.env

# Remove backups older than 90 days (EN 50128: 10-year retention — keep 90 days locally)
find $BACKUP_DIR -type f -mtime +90 -delete

echo "$(date) - Backup completed" >> /var/log/cortex/backup.log
```

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /opt/cortex/scripts/backup.sh
```

## Security Hardening

### 1. Firewall Configuration

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 2. Fail2Ban Setup

```bash
sudo apt install fail2ban -y
```

Create `/etc/fail2ban/jail.local`:

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
```

### 3. Application Security Headers

Cortex already sets security headers via middleware. Ensure nginx config includes them (shown in step 7 above).

## Log Rotation

Create `/etc/logrotate.d/cortex`:

```
/var/log/cortex/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 cortex cortex
    sharedscripts
    postrotate
        systemctl reload cortex
    endscript
}
```

## EN 50128 Compliance Notes

### Evidence Retention
- Evidence artifacts (`.cortex/evidence/`) should be backed up and retained for the software lifecycle duration per EN 50128 requirements
- Soft-delete on assets enforces 10-year retention; ensure backups cover this period

### Audit Log Integrity
- Audit logs use HMAC-SHA256 signatures; any tampering is detectable
- Do not modify `.cortex/` evidence files after creation

### T2 Tool Qualification
- Regression guard and T2 qualification run automatically in CI on every push
- After intentional code changes, run `python -m cortex.regression_guard generate` and commit the updated `.cortex/expected_hashes.json`

## Performance Tuning

### Application Workers

```bash
# Recommended: (2 x CPU cores) + 1
# For 4 CPU cores: 9 workers
gunicorn cortex.api:app --workers 9 --worker-class uvicorn.workers.UvicornWorker
```

### SQLite vs PostgreSQL

For single-instance deployments, SQLite is sufficient and recommended for simplicity:

```bash
DATABASE_URL=sqlite:///./cortex.db
```

For multi-worker or distributed deployments, switch to PostgreSQL:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/cortex
```
