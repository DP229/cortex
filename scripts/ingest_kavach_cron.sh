#!/usr/bin/env bash
# KAVACH Scheduled Ingestion Script
#
# Production wrapper for cortex/ingest_kavach.py with:
#   - Lockfile to prevent concurrent runs
#   - Locking to skip if a run is in progress
#   - Logging to /var/log/cortex-kavach-ingest.log (or fallback to /tmp)
#   - Rotation-aware: skips ingest if a successful run happened within the
#     INGEST_MIN_INTERVAL_SECS window
#   - Exit codes: 0=success, 1=in-progress, 2=ingest-error, 3=interval-not-elapsed
#
# Install as cron:
#   0 * * * * /opt/cortex/scripts/ingest_kavach_cron.sh
#   (runs every hour; INGEST_MIN_INTERVAL_SECS=3600 ensures only one run/hour)
#
# Or run as systemd timer — see scripts/ingest_kavach.timer
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK_FILE="/var/lock/cortex-kavach-ingest.lock"
LOG_FILE="${CORTEX_KAVACH_INGEST_LOG:-/tmp/cortex-kavach-ingest.log}"
STATE_FILE="/tmp/cortex-kavach-last-run"
INGEST_MIN_INTERVAL_SECS="${INGEST_MIN_INTERVAL_SECS:-3600}"

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log() { echo "[$(date -Is)] $*" | tee -a "$LOG_FILE" >&2 ; }

# 1. Lockfile check
if [ -f "$LOCK_FILE" ]; then
    if kill -0 "$(cat "$LOCK_FILE")" 2>/dev/null; then
        log "Another ingest is in progress (PID $(cat "$LOCK_FILE")). Exiting."
        exit 1
    else
        log "Stale lockfile from dead PID $(cat "$LOCK_FILE"). Removing."
        rm -f "$LOCK_FILE"
    fi
fi
echo "$$" > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# 2. Interval check
if [ -f "$STATE_FILE" ]; then
    LAST_RUN=$(cat "$STATE_FILE")
    NOW=$(date +%s)
    ELAPSED=$((NOW - LAST_RUN))
    if [ "$ELAPSED" -lt "$INGEST_MIN_INTERVAL_SECS" ]; then
        log "Last run was $ELAPSED seconds ago; min interval is $INGEST_MIN_INTERVAL_SECS s. Skipping."
        exit 3
    fi
fi

# 3. Set required env
export ENCRYPTION_KEY="${ENCRYPTION_KEY:-ZGV2LW9ubHktbm90LWZvci1wcm9kdWN0aW9uLTMyYi1rZXk=}"
export CORTEX_DOCUMENT_STORAGE="${CORTEX_DOCUMENT_STORAGE:-$CORTEX_ROOT/data/cortex_documents}"
mkdir -p "$CORTEX_DOCUMENT_STORAGE"

cd "$CORTEX_ROOT"

# 4. Run the ingest with --skip-existing (idempotent)
log "Starting KAVACH ingest (skip-existing mode)"
if ./.venv/bin/python cortex/ingest_kavach.py --skip-existing >> "$LOG_FILE" 2>&1; then
    date +%s > "$STATE_FILE"
    log "KAVACH ingest completed successfully"
    exit 0
else
    log "KAVACH ingest FAILED (exit $?)"
    exit 2
fi
