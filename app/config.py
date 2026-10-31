import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env when present (never commit .env). On Vercel, use project Env vars only.
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# True on Vercel / when filesystem must be treated as read-only for secrets & index writes
IS_SERVERLESS = bool(
    os.getenv("VERCEL")
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    or os.getenv("MURSHID_READONLY", "").strip().lower() in ("1", "true", "yes")
)


def resolve_knowledge_dir() -> Path:
    """
    Canonical folder name is Knowledge/ (case-sensitive on Linux).
    On case-insensitive Windows, knowledge/ and Knowledge/ may resolve to the same path.
    Prefer an existing directory; default to Knowledge for new setups.
    """
    for name in ("Knowledge", "knowledge"):
        p = BASE_DIR / name
        if p.is_dir():
            return p
    return BASE_DIR / "Knowledge"


KNOWLEDGE_DIR = resolve_knowledge_dir()
DATA_DIR = BASE_DIR / "data"
BUILT_INDEX_FILE = DATA_DIR / "knowledge_index.json"

# Free-tier oriented default (newer Flash-Lite for new projects)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"

# Request limits (in-memory; not a substitute for edge rate limiting on multi-instance Vercel)
MAX_QUERY_CHARS = int(os.getenv("MAX_QUERY_CHARS", "2000"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))


def get_gemini_api_key() -> str:
    """Server-side only. Never expose via API responses."""
    return os.getenv("GEMINI_API_KEY", "").strip()
