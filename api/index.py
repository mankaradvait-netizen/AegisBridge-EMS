import os
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# On Vercel serverless environment, the filesystem is read-only except /tmp
if os.environ.get("VERCEL"):
    tmp_ledger = Path("/tmp/audit_trail.jsonl")
    bundled_ledger = ROOT_DIR / "audit_trail.jsonl"
    if not tmp_ledger.exists() and bundled_ledger.exists():
        try:
            shutil.copyfile(bundled_ledger, tmp_ledger)
        except Exception:
            pass
    os.environ.setdefault("AEGIS_AUDIT_LEDGER_PATH", str(tmp_ledger))

from src.api import app
