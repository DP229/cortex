#!/usr/bin/env python3
"""
IBM ELM / DOORS Bidirectional Sync Demo

Demonstrates the full DOORS ↔ Cortex sync workflow using ReqIF as the
interchange format. This is a proof-of-concept — production usage requires
a live ELM server with OIDC credentials configured in cortex/ibm_elm/config.py.

Usage:
    python cortex/elm_sync_demo.py export    # Cortex → DOORS ReqIF
    python cortex/elm_sync_demo.py import    # DOORS ReqIF → Cortex
    python cortex/elm_sync_demo.py status    # Show current sync state
    python cortex/elm_sync_demo.py roundtrip # Full round-trip
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from uuid import uuid4

CORTEX_DEMO_DIR = Path("/home/durga/Documents/cortex/cortex-demo")
REQIF_FILE = CORTEX_DEMO_DIR / "kavach-rtm.reqif"
DOORS_REQIF_FILE = CORTEX_DEMO_DIR / "kavach-doors-roundtrip.reqif"
ELM_STATUS_FILE = CORTEX_DEMO_DIR / "elm-sync-status.json"
ELM_CONFIG_TEMPLATE = CORTEX_DEMO_DIR / "elm-config-prod.json"


def _count_reqif_entities(reqif_path: Path) -> dict:
    """Count entities in a ReqIF file."""
    if not reqif_path.exists():
        return {"exists": False}
    text = reqif_path.read_text()
    return {
        "exists": True,
        "size_bytes": len(text),
        "spec_objects": text.count("SPEC-OBJECT") - text.count("</SPEC-OBJECT"),
        "spec_relations": text.count("SPEC-RELATION") - text.count("</SPEC-RELATION"),
        "specifications": text.count("SPECIFICATION") - text.count("</SPECIFICATION"),
        "datatypes": text.count("STRING-DATATYPE") + text.count("INTEGER-DATATYPE"),
    }


def cmd_status() -> int:
    """Show current ELM sync state."""
    print("=" * 60)
    print("IBM ELM / DOORS Sync Status")
    print("=" * 60)
    print()
    print(f"Cortex ReqIF export:  {REQIF_FILE}")
    if REQIF_FILE.exists():
        e = _count_reqif_entities(REQIF_FILE)
        print(f"  exists: {e['exists']}")
        print(f"  size: {e['size_bytes']} bytes")
        print(f"  spec_objects: {e['spec_objects']}")
        print(f"  spec_relations: {e['spec_relations']}")
        print(f"  specifications: {e['specifications']}")
    else:
        print("  (not yet exported)")
    print()
    print(f"ELM status file: {ELM_STATUS_FILE}")
    if ELM_STATUS_FILE.exists():
        s = json.loads(ELM_STATUS_FILE.read_text())
        print(json.dumps(s, indent=2))
    else:
        print("  (no sync history yet)")
    return 0


def cmd_export() -> int:
    """Cortex → DOORS ReqIF export."""
    print("=" * 60)
    print("Cortex → DOORS Export (ReqIF 1.0)")
    print("=" * 60)
    print()

    # Use the existing ReqIF export endpoint
    import urllib.request

    cookie_token_path = Path("/tmp/cortex-cookies.txt")
    if not cookie_token_path.exists():
        print("ERROR: not logged in. Run: curl -X POST http://localhost:8080/auth/login ...")
        return 1
    cookie = cookie_token_path.read_text().split("cortex_auth_token\t")[-1].split("\n")[0]
    req = urllib.request.Request(
        "http://localhost:8080/requirements/export-reqif",
        headers={"Cookie": f"cortex_auth_token={cookie}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            reqif_data = r.read()
    except Exception as e:
        print(f"ERROR fetching from Cortex: {e}")
        return 1

    DOORS_REQIF_FILE.write_bytes(reqif_data)
    e = _count_reqif_entities(DOORS_REQIF_FILE)
    print(f"✓ Exported ReqIF to {DOORS_REQIF_FILE.name}")
    print(f"  size: {e['size_bytes']} bytes")
    print(f"  spec_objects (requirements): {e['spec_objects']}")
    print(f"  specifications: {e['specifications']}")
    print()
    print("Next step: import this file into IBM DOORS Next Generation via")
    print("  File → Import → ReqIF → select kavach-doors-roundtrip.reqif")
    return 0


def cmd_roundtrip() -> int:
    """Full round-trip: Cortex → DOORS ReqIF → re-import into Cortex."""
    print("=" * 60)
    print("Full DOORS ↔ Cortex Round-Trip")
    print("=" * 60)
    print()

    rc = cmd_export()
    if rc != 0:
        return rc

    print()
    print("=" * 60)
    print("Simulated DOORS round-trip — modifying the ReqIF in transit")
    print("=" * 60)
    print()

    # Simulate DOORS modifying the file (add a comment + a status change)
    text = DOORS_REQIF_FILE.read_text()
    text += (
        f"\n  <!-- DOORS round-trip annotation: re-imported at "
        f"{datetime.utcnow().isoformat()}Z, project: KAVACH_PROD -->\n"
    )
    DOORS_REQIF_FILE.write_text(text)
    print(f"✓ Simulated DOORS annotation: {DOORS_REQIF_FILE.name}")
    print()

    # Now demonstrate that Cortex can re-import the ReqIF (this is what the
    # 'import-document' endpoint would do if it supported ReqIF; the
    # current endpoint supports text-based requirements, not ReqIF XML)
    print("=" * 60)
    print("Cortex re-import of DOORS-annotated ReqIF")
    print("=" * 60)
    print()
    print(f"  File: {DOORS_REQIF_FILE.name}")
    print(f"  Size: {DOORS_REQIF_FILE.stat().st_size} bytes")
    print()
    print("  NOTE: The current Cortex /requirements/import-document endpoint")
    print("  parses text and PDF documents via Ollama. ReqIF XML re-import is")
    print("  handled by the ibm_elm/reqif/ module (see ReqIFImporter class).")
    print("  To enable in production, set ELM_ENABLED=true in .env and provide")
    print("  OIDC credentials in cortex/ibm_elm/config.py.")
    return 0


def cmd_import() -> int:
    """DOORS ReqIF → Cortex import."""
    print("=" * 60)
    print("DOORS ReqIF → Cortex Import")
    print("=" * 60)
    print()
    if not DOORS_REQIF_FILE.exists():
        print("ERROR: no DOORS ReqIF file. Run 'export' first.")
        return 1
    e = _count_reqif_entities(DOORS_REQIF_FILE)
    print(f"File: {DOORS_REQIF_FILE.name}")
    print(f"  spec_objects: {e['spec_objects']}")
    print()
    print("Production import path:")
    print("  1. cortex/ibm_elm/reqif/importer.py — ReqIFImporter class")
    print("  2. Maps ReqIF SPEC-OBJECT attrs to Cortex Requirement fields")
    print("  3. Creates/updates requirements via the requirements_routes API")
    print()
    print("See cortex/ibm_elm/reqif/ for the importer implementation.")
    return 0


def cmd_save_status() -> int:
    """Persist a sync status snapshot."""
    e = _count_reqif_entities(REQIF_FILE)
    status = {
        "last_export_at": datetime.utcnow().isoformat() + "Z",
        "cortex_reqif": str(REQIF_FILE),
        "cortex_entities": e,
        "elm_enabled": os.getenv("ELM_ENABLED", "false"),
        "notes": "Production ELM sync requires ELM_ENABLED=true and OIDC credentials in cortex/ibm_elm/config.py",
    }
    ELM_STATUS_FILE.write_text(json.dumps(status, indent=2))
    print(f"✓ Wrote sync status to {ELM_STATUS_FILE}")

    # Also write a production config template
    ELM_CONFIG_TEMPLATE.write_text(json.dumps({
        "enabled": True,
        "jts_url": "https://jts.example.com/jts",
        "rm_url": "https://jts.example.com/rm",
        "ccm_url": "https://jts.example.com/ccm",
        "qm_url": "https://jts.example.com/qm",
        "gcm_url": "https://jts.example.com/gcm",
        "project_area_name": "KAVACH_ATP",
        "project_area_uuid": "<set after first discovery>",
        "auth_mode": "oidc",
        "oidc_issuer_url": "https://auth.example.com/oauth2",
        "oidc_client_id": "<from secure vault>",
        "oidc_client_secret_secret_ref": "vault://elm/client_secret",
        "verify_ssl": True,
        "dry_run_default": True,
        "max_sync_batch": 100,
        "note": "All OIDC secrets must be stored in a secret manager, not in this file"
    }, indent=2))
    print(f"✓ Wrote ELM config template to {ELM_CONFIG_TEMPLATE}")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = sys.argv[1]
    if cmd == "status":
        return cmd_status()
    elif cmd == "export":
        return cmd_export()
    elif cmd == "import":
        return cmd_import()
    elif cmd == "roundtrip":
        return cmd_roundtrip()
    elif cmd == "save-status":
        return cmd_save_status()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
