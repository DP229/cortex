# Healthcare Compliance Agent - Deployment Guide

## Prerequisites

### System Requirements
- **OS:** Linux (Ubuntu 20.04+ recommended)
- **Python:** 3.9+
- **PostgreSQL:** 13+
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 10GB minimum for database, additional for document storage

### Required Software
- PostgreSQL 13+
- Python 3.9+
- pip / poetry
- nginx (for production)
- SSL certificate

## Environment Setup

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Python
sudo apt install python3.9 python3.9-venv python3-pip -y

# Install additional packages
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 2. Create Database

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE cortex_healthcare;
CREATE USER cortex_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE cortex_healthcare TO cortex_user;

# Exit PostgreSQL
\q
```

### 3. Configure PostgreSQL

Edit `/etc/postgresql/13/main/postgresql.conf`:

```conf
# Connection settings
listen_addresses = 'localhost'
max_connections = 200

# Memory
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# Logging
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_statement = 'mod'

# SSL (required for HIPAA)
ssl = on
```

Create `/etc/postgresql/13/main/pg_hba.conf` entries:

```conf
# Allow connections from application server
host    cortex_healthcare    cortex_user    127.0.0.1/32    md5
hostssl cortex_healthcare    cortex_user    127.0.0.1/32    md5
```

### 4. Set Up Application

```bash
# Create application directory
sudo mkdir -p /opt/cortex
sudo chown $USER:$USER /opt/cortex
cd /opt/cortex

# Clone repository
git clone <repository-url> .

# Create virtual environment
python3.9 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install additional production dependencies
pip install gunicorn uvicorn[standard] psycopg2-binary
```

### 5. Environment Variables

Create `.env` file:

```bash
# Database
DATABASE_URL=postgresql://cortex_user:your_secure_password@localhost/cortex_healthcare

# Security
ENCRYPTION_KEY=<generate-with-openssl-rand-base64-32>
JWT_SECRET=<generate-with-openssl-rand-base64-32>

# Application
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com

# Document Storage
DOCUMENT_STORAGE_PATH=/var/lib/cortex/documents

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/cortex/app.log

# Rate Limiting
RATE_LIMIT_LOGIN=5/300
RATE_LIMIT_API=100/60
```

Generate secure keys:

```bash
# Generate encryption key
openssl rand -base64 32

# Generate JWT secret
openssl rand -base64 32
```

### 6. Initialize Database

```bash
# Create document storage directory
sudo mkdir -p /var/lib/cortex/documents
sudo chown $USER:$USER /var/lib/cortex/documents

# Create log directory
sudo mkdir -p /var/log/cortex
sudo chown $USER:$USER /var/log/cortex

# Run database initialization
cd /opt/cortex
source venv/bin/activate
python scripts/init_db.py
```

### 7. Configure Systemd Service

Create `/etc/systemd/system/cortex.service`:

```ini
[Unit]
Description=Healthcare Compliance Agent
After=network.target postgresql.service

[Service]
Type=notify
User=cortex
Group=cortex
WorkingDirectory=/opt/cortex
Environment="PATH=/opt/cortex/venv/bin"
ExecStart=/opt/cortex/venv/bin/uvicorn cortex.main:app --host 127.0.0.1 --port 8080 --workers 4
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cortex
sudo systemctl start cortex
```

### 8. Configure Nginx

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
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

    # Proxy to application
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Rate limiting
        limit_req zone=api burst=200 nodelay;
    }

    # Login rate limiting
    location /auth/login {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        limit_req zone=login burst=10 nodelay;
    }

    # Static files (if any)
    location /static {
        alias /opt/cortex/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/cortex /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 9. SSL Certificate

```bash
# Obtain Let's Encrypt certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 10. Monitoring Setup

Create `/etc/cortex/monitoring.yml`:

```yaml
# Prometheus metrics endpoint
- job_name: 'cortex'
  static_configs:
    - targets: ['localhost:8080']
  
  # Scrape interval
  scrape_interval: 30s
  
  # Metrics path
  metrics_path: /metrics
```

### 11. Backup Configuration

Create backup script `/opt/cortex/scripts/backup.sh`:

```bash
#!/bin/bash

# Backup script for Healthcare Compliance Agent

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/cortex"
DB_NAME="cortex_healthcare"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U cortex_user $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Backup documents
tar -czf $BACKUP_DIR/documents_$DATE.tar.gz /var/lib/cortex/documents

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/cortex/.env

# Remove backups older than 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

# Log
echo "$(date) - Backup completed" >> /var/log/cortex/backup.log
```

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /opt/cortex/scripts/backup.sh
```

## Database Optimization

### Create Indexes

```sql
-- Connect to database
\c cortex_healthcare

-- Create performance indexes
CREATE INDEX CONCURRENTLY idx_audit_log_user_time ON audit_log(user_id, timestamp DESC);
CREATE INDEX CONCURRENTLY idx_audit_log_patient_time ON audit_log(patient_id, timestamp DESC);
CREATE INDEX CONCURRENTLY idx_document_patient ON documents(patient_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_consent_patient_date ON consent_records(patient_id, consent_date DESC);
CREATE INDEX CONCURRENTLY idx_icd10_search ON icd10_codes USING gin(to_tsvector('english', description));
CREATE INDEX CONCURRENTLY idx_cpt_search ON cpt_codes USING gin(to_tsvector('english', description));

-- Analyze tables
ANALYZE audit_log;
ANALYZE documents;
ANALYZE consent_records;
ANALYZE patients;
ANALYZE users;
```

### Configure Autovacuum

```sql
-- Enable autovacuum
ALTER SYSTEM SET autovacuum = on;
ALTER SYSTEM SET autovacuum_max_workers = 4;

-- For audit_log table (high insert rate)
ALTER TABLE audit_log SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE audit_log SET (autovacuum_analyze_scale_factor = 0.05);

-- For patient tables (moderate change rate)
ALTER TABLE patients SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE consent_records SET (autovacuum_vacuum_scale_factor = 0.1);
```

## Security Hardening

### 1. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
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
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
```

### 3. Application Security

```python
# Add to main.py

from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

## HIPAA Compliance Checklist

### Administrative Safeguards
- [ ] Access control procedures documented
- [ ] Audit control procedures documented
- [ ] Workforce training completed
- [ ] Security incident procedures documented
- [ ] Contingency plan documented

### Physical Safeguards
- [ ] Facility access controls implemented
- [ ] Workstation use policies documented
- [ ] Device and media controls implemented

### Technical Safeguards
- [x] Access control (authentication + authorization)
- [x] Audit controls (6-year retention)
- [x] Integrity controls (encryption + validation)
- [x] Transmission security (HTTPS/TLS)
- [x] Encryption (AES-256-GCM at rest)

## Monitoring & Logging

### Application Logs

```bash
# /var/log/cortex/app.log
# /var/log/cortex/security.log
# /var/log/cortex/audit.log
```

### Log Rotation

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

## Performance Tuning

### Application Workers

```bash
# Recommended: (2 x CPU cores) + 1
# For 4 CPU cores: 9 workers
gunicorn cortex.main:app --workers 9 --worker-class uvicorn.workers.UvicornWorker
```

### Database Connection Pool

```python
# In database configuration
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 10
SQLALCHEMY_POOL_TIMEOUT = 30
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_POOL_PRE_PING = True
```

## Maintenance

### Daily Tasks
- Check application logs
- Monitor database health
- Verify backup completion
- Review security alerts

### Weekly Tasks
- Update security patches
- Review audit logs
- Check disk space
- Update dependencies (security patches only)

### Monthly Tasks
- Full security scan
- Performance review
- Backup restoration test
- HIPAA compliance review

## Troubleshooting

### Common Issues

**Database Connection Errors:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connection limit
SELECT count(*) FROM pg_stat_activity;
```

**Authentication Failures:**
```bash
# Check logs
tail -f /var/log/cortex/app.log

# Verify encryption key
echo $ENCRYPTION_KEY | wc -c
```

**Performance Issues:**
```bash
# Check database connections
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;

# Check slow queries
SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
```

### Health Check Endpoints

```bash
# Application health
curl https://yourdomain.com/health

# Database health
curl https://yourdomain.com/health/database

# Metrics
curl https://yourdomain.com/metrics
```

## Security Audit Checklist

- [ ] SSL/TLS enabled
- [ ] Firewall configured
- [ ] Rate limiting enabled
- [ ] Security headers set
- [ ] Encryption at rest
- [ ] Audit logging enabled
- [ ] Authentication required
- [ ] Authorization enforced
- [ ] PHI detection active
- [ ] Consent management active
- [ ] Backup encryption enabled
- [ ] Access logs monitored

## Support

For issues or questions:
- Check logs: `/var/log/cortex/`
- Review documentation: `/opt/cortex/docs/`
- HIPAA compliance: Contact compliance officer

---

**IMPORTANT:** This deployment must be reviewed by your security and compliance teams before production use. All HIPAA requirements must be validated for your specific use case.