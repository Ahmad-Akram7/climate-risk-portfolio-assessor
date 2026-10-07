"""Central configuration. Everything is overridable via environment variables / .env."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        # Support the common ``KEY=value  # explanation`` format without
        # accidentally sending the explanation as part of the credential.
        v = v.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


_load_dotenv()

DATA_DIR = Path(os.getenv("CRPA_DATA_DIR", ROOT / "data"))
HAZARD_DIR = DATA_DIR / "hazards"
OUTPUT_DIR = Path(os.getenv("CRPA_OUTPUT_DIR", ROOT / "outputs"))
CACHE_DIR = Path(os.getenv("CRPA_CACHE_DIR", ROOT / ".cache"))

MAX_ASSETS = int(os.getenv("CRPA_MAX_ASSETS", "500"))
CACHE_TTL_DAYS = int(os.getenv("CRPA_CACHE_TTL_DAYS", "30"))
HTTP_TIMEOUT = float(os.getenv("CRPA_HTTP_TIMEOUT", "6"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
OFFLINE = os.getenv("CRPA_OFFLINE", "0") == "1"  # skip all network calls
MAX_WORKERS = int(os.getenv("CRPA_MAX_WORKERS", "8"))


def key(name: str) -> str | None:
    """Read an API key from the environment (set in .env or the dashboard)."""
    v = os.getenv(name)
    if not v:
        return None
    # API tokens are single-line values; remove accidental copy/paste whitespace.
    return "".join(v.split()) if name.endswith(("_API_KEY", "_TOKEN")) else v


# LLM (OpenAI-compatible endpoint; defaults to NVIDIA Nemotron 3.5 Lightning)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

for _d in (HAZARD_DIR, OUTPUT_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
