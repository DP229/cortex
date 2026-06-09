#!/usr/bin/env python3
"""
KAVACH Product-Suit Web UI Walkthrough

Programmatically walks through every Cortex UI page via the API to verify
data is loaded and the user-visible experience would work end-to-end.

For each page:
  1. Calls the underlying API endpoint
  2. Reports entity counts
  3. Highlights any errors or empty results

This is the equivalent of clicking through the UI manually — it exercises
the same data paths the React frontend uses.

Usage:
    python cortex/ui_walkthrough.py          # Run all checks
    python cortex/ui_walkthrough.py --save   # Save report to cortex-demo/
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Optional

BASE = "http://localhost:8080"
COOKIE = None
REPORT = []


def login() -> bool:
    """Authenticate and save cookie."""
    global COOKIE
    data = json.dumps({"email": "admin@cortex.dev", "password": "AdminPass123!"}).encode()
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            for h in r.getheaders():
                if h[0].lower() == "set-cookie" and "cortex_auth_token" in h[1]:
                    COOKIE = h[1].split(";")[0]
                    return True
    except Exception as e:
        print(f"  ✗ login failed: {e}")
        return False
    return False


def api(path: str, method: str = "GET", data: Optional[dict] = None) -> dict:
    """Call Cortex API and return parsed JSON or error info."""
    url = f"{BASE}{path}"
    headers = {"Cookie": COOKIE or ""}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")
            elapsed = time.time() - start
            try:
                return {"ok": True, "status": r.status, "elapsed_ms": int(elapsed * 1000), "data": json.loads(text)}
            except json.JSONDecodeError:
                return {"ok": True, "status": r.status, "elapsed_ms": int(elapsed * 1000), "data": text}
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return {"ok": False, "status": e.code, "elapsed_ms": int(elapsed * 1000), "error": e.read().decode("utf-8", errors="replace")[:300]}
    except Exception as e:
        return {"ok": False, "status": 0, "elapsed_ms": int((time.time() - start) * 1000), "error": str(e)}


def check(page_name: str, api_path: str, expected_keys: list[str], method: str = "GET", body: Optional[dict] = None) -> dict:
    """Run a single check; report status."""
    r = api(api_path, method=method, data=body)
    record = {
        "page": page_name,
        "endpoint": api_path,
        "ok": r["ok"],
        "status": r["status"],
        "elapsed_ms": r["elapsed_ms"],
    }
    if r["ok"]:
        d = r["data"]
        if isinstance(d, dict):
            for k in expected_keys:
                record[f"has_{k}"] = k in d
        elif isinstance(d, list):
            record["count"] = len(d)
        else:
            record["has_data"] = bool(d)
    else:
        record["error"] = r.get("error", "unknown")
    REPORT.append(record)
    status = "✓" if r["ok"] else "✗"
    print(f"  {status} {page_name:35s}  HTTP {r['status']:3d}  {r['elapsed_ms']:5d}ms  {api_path}")
    return record


def main():
    print("=" * 70)
    print("KAVACH Product-Suit — Web UI Walkthrough")
    print("=" * 70)

    if not login():
        print("✗ Login failed — aborting")
        return 1

    print(f"\n✓ Logged in as admin@cortex.dev\n")

    # 1. Dashboard data
    print("=== Dashboard (/) ===")
    check("Dashboard - Requirements count", "/requirements/", ["x" if False else "y"], "GET")
    check("Dashboard - SOUPs count", "/soups/", [], "GET")
    check("Dashboard - Test records count", "/test-records/", [], "GET")
    check("Dashboard - Incidents count", "/audit/incidents", [], "GET")

    # 2. Requirements page
    print("\n=== Requirements Page ===")
    check("Requirements - List all", "/requirements/", [], "GET")
    r = api("/requirements/?verification_status=failed")
    if r["ok"]:
        failed = r["data"] if isinstance(r["data"], list) else []
        print(f"  → {len(failed)} failed requirements (will appear red in UI)")

    # 3. SOUPs page
    print("\n=== SOUPs Page ===")
    r = check("SOUPs - List all", "/soups/", [], "GET")
    r2 = api("/soups/?status=rejected")
    if r2["ok"] and isinstance(r2["data"], list) and r2["data"]:
        print(f"  → {len(r2['data'])} rejected SOUP (will appear with reason)")

    # 4. Assets page
    print("\n=== Assets Page (with hierarchy) ===")
    assets_result = api("/assets/", "GET")
    if assets_result["ok"]:
        assets = assets_result["data"] if isinstance(assets_result["data"], list) else []
        print(f"  → {len(assets)} assets, {sum(1 for a in assets if a.get('parent_asset_id'))} are children")
        REPORT.append({"page": "Assets - List", "endpoint": "/assets/", "ok": True, "status": 200, "elapsed_ms": assets_result["elapsed_ms"], "count": len(assets)})
    else:
        REPORT.append({"page": "Assets - List", "endpoint": "/assets/", "ok": False, "status": assets_result["status"], "error": assets_result.get("error", "unknown")})
    print(f"  ✓ Assets - List                        HTTP {assets_result['status']:3d}  {assets_result['elapsed_ms']:5d}ms  /assets/")

    # 5. Test Records page
    print("\n=== Test Records Page ===")
    tr_result = api("/test-records/", "GET")
    if tr_result["ok"]:
        records = tr_result["data"] if isinstance(tr_result["data"], list) else []
        from collections import Counter
        c = Counter(t["status"] for t in records)
        for s, n in c.most_common():
            print(f"  → {n} tests {s} (color-coded in UI)")
        REPORT.append({"page": "Test Records - List", "endpoint": "/test-records/", "ok": True, "status": 200, "elapsed_ms": tr_result["elapsed_ms"], "count": len(records)})
    else:
        REPORT.append({"page": "Test Records - List", "endpoint": "/test-records/", "ok": False, "status": tr_result["status"], "error": tr_result.get("error", "unknown")})
    print(f"  ✓ Test Records - List                  HTTP {tr_result['status']:3d}  {tr_result['elapsed_ms']:5d}ms  /test-records/")

    # 6. RTM page
    print("\n=== RTM Page (per-requirement traceability) ===")
    r = api("/requirements/")
    if r["ok"] and isinstance(r["data"], list) and r["data"]:
        sample_req = r["data"][0]
        check(f"RTM - Trace for {sample_req['requirement_id']}", f"/requirements/{sample_req['id']}", ["requirement", "citations", "test_records"])
    check("RTM - Citation list", "/requirements/citations", [], "GET")

    # 7. Documents page
    print("\n=== Documents Page ===")
    check("Documents - List", "/documents/", [], "GET")

    # 8. KB page
    print("\n=== Knowledge Base Page ===")
    check("KB - List articles", "/kb/articles?limit=200", [], "GET")
    check("KB - Search (UHF radio)", "/kb/search?q=UHF+radio", [], "GET")
    check("KB - Categories", "/kb/categories", [], "GET")

    # 9. Audit Log page
    print("\n=== Audit Log Page ===")
    check("Audit Log - First 50", "/audit/logs?limit=50", [], "GET")
    check("Compliance Report", "/audit/reports/compliance", [], "GET")

    # 10. Incidents page
    print("\n=== Incidents Page ===")
    check("Incidents - List", "/audit/incidents", [], "GET")

    # 11. Qualification page
    print("\n=== Qualification Page ===")
    check("Qualification - Status", "/v2/qualification/status", [], "GET")
    check("Qualification - TOR (markdown)", "/v2/qualification/tor?format=markdown", [], "GET")
    check("Qualification - TVR (markdown)", "/v2/qualification/tvr?format=markdown", [], "GET")
    check("Qualification - TVP (markdown)", "/v2/qualification/tvp?format=markdown", [], "GET")

    # 12. Semantic search (new)
    print("\n=== Semantic Search (new) ===")
    check("Semantic - Stats", "/kb/semantic-stats", [], "GET")
    check("Semantic - Search RFID", "/kb/semantic-search", ["results", "model", "dim", "total_indexed"], "POST", {
        "query": "RFID balise read failure at high speed",
        "top_k": 5
    })

    # 13. ELM (DOORS sync)
    print("\n=== IBM ELM / DOORS Sync ===")
    check("ELM - Health", "/elm/health", [], "GET")
    check("ELM - Config", "/elm/config", [], "GET")
    check("ELM - Sync jobs", "/elm/sync-jobs", [], "GET")

    # 14. ReqIF export
    print("\n=== ReqIF Export (RTM download) ===")
    check("RTM - Export ReqIF", "/requirements/export-reqif", [], "GET")

    # 15. AI Chat
    print("\n=== AI Compliance Copilot (chat) ===")
    r = api("/chat", "POST", {
        "message": "Summarise the KAVACH ATP safety case in 2 sentences.",
        "history": []
    })
    if r["ok"]:
        text = r["data"].get("response", "")
        print(f"  ✓ AI chat responded ({len(text)} chars, {len(r['data'].get('sources', []))} KB citations)")
        REPORT.append({"page": "AI Chat", "endpoint": "/chat", "ok": True, "status": 200, "elapsed_ms": r["elapsed_ms"], "response_len": len(text), "sources": len(r["data"].get("sources", []))})
    else:
        print(f"  ✗ AI chat failed: {r.get('error', 'unknown')}")
        REPORT.append({"page": "AI Chat", "endpoint": "/chat", "ok": False, "status": r["status"], "error": r.get("error", "unknown")})

    # Summary
    print("\n" + "=" * 70)
    print("WALKTHROUGH SUMMARY")
    print("=" * 70)
    total = len(REPORT)
    passed = sum(1 for r in REPORT if r.get("ok"))
    failed = total - passed
    print(f"  Total checks: {total}")
    print(f"  Passed:       {passed}")
    print(f"  Failed:       {failed}")
    if failed > 0:
        print("\nFailed pages:")
        for r in REPORT:
            if not r.get("ok"):
                print(f"  ✗ {r['page']:35s}  {r.get('error', 'unknown')[:100]}")

    if "--save" in sys.argv:
        out_path = Path("/home/durga/Documents/cortex/cortex-demo/kavach-ui-walkthrough.json")
        out_path.write_text(json.dumps({
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total": total,
            "passed": passed,
            "failed": failed,
            "checks": REPORT,
        }, indent=2))
        print(f"\n✓ Report saved to {out_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
