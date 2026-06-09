# Ingestion Scripts

Production wrappers for the KAVACH knowledge-injection pipeline.

## `ingest_kavach_cron.sh` (bash)

Hourly-safe wrapper around `cortex/ingest_kavach.py --skip-existing` with:
- Lockfile to prevent concurrent runs
- Minimum-interval guard (`INGEST_MIN_INTERVAL_SECS`)
- Centralised logging (`CORTEX_KAVACH_INGEST_LOG`)
- Trap-based lock cleanup

### Install as cron (every hour)
```cron
0 * * * * /opt/cortex/scripts/ingest_kavach_cron.sh
```

### Install as systemd
```bash
cp scripts/ingest_kavach_cron.sh /opt/cortex/scripts/
cp scripts/ingest_kavach.service /etc/systemd/system/
cp scripts/ingest_kavach.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ingest_kavach.timer
systemctl list-timers ingest_kavach.timer
```

### Environment variables
| Var | Default | Purpose |
|---|---|---|
| `INGEST_MIN_INTERVAL_SECS` | 3600 | Minimum seconds between successful runs |
| `CORTEX_KAVACH_INGEST_LOG` | /tmp/cortex-kavach-ingest.log | Where to log |
| `ENCRYPTION_KEY` | dev placeholder | AES-256 key for document encryption |
| `CORTEX_DOCUMENT_STORAGE` | ./data/cortex_documents | Where to write encrypted docs |

### Exit codes
- `0` — success
- `1` — another run is in progress (lockfile)
- `2` — ingest itself failed
- `3` — minimum interval not elapsed

## `ingest_kavach.service` + `ingest_kavach.timer` (systemd)

Production timer definition. Run every hour on the hour with 5-min slack.

## `ingest_kavach_cron.sh` behaviour notes

- Idempotent: re-running on the same data is a no-op (checksum + title dedup)
- Safe to run in parallel across multiple hosts (each has its own lockfile)
- Will skip if a run completed in the last `INGEST_MIN_INTERVAL_SECS` seconds
- Writes a state file (`/tmp/cortex-kavach-last-run`) for the interval check
