"""config.py — D8+H2 fix: single source of truth for all paths."""
from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).parent.resolve()

_env = PROJECT_ROOT / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

def get_data_dir() -> Path:
    d = Path(os.environ.get("SUPPLIER_PIPELINE_DATA_DIR", PROJECT_ROOT / "data")).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_db_path() -> Path:
    return get_data_dir() / "supplier_risk.db"

def get_chroma_path() -> Path:
    p = get_data_dir() / "chroma"; p.mkdir(parents=True, exist_ok=True); return p

def get_reports_dir() -> Path:
    r = get_data_dir() / "reports"; r.mkdir(parents=True, exist_ok=True); return r

def get_lm_studio_url() -> str:
    return os.environ.get("LM_STUDIO_URL", "http://localhost:1234").rstrip("/")

def get_lm_studio_model() -> str:
    return os.environ.get("LM_STUDIO_MODEL", "gpt-oss-20b")

def get_lm_studio_timeout() -> int:
    try: return int(os.environ.get("LM_STUDIO_TIMEOUT", "120"))
    except ValueError: return 120
