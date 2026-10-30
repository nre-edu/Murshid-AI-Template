#!/usr/bin/env python3
"""Build-time knowledge index for Daleel (Vercel / local production builds).

Usage:
  python scripts/build_knowledge_index.py

Indexes all supported Markdown under Knowledge/, excluding Knowledge/_examples/
and test-question files. Writes data/knowledge_index.json for the runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.local_knowledge import build_index_payload, write_built_index  # noqa: E402
from app.config import BUILT_INDEX_FILE, KNOWLEDGE_DIR  # noqa: E402


def main() -> int:
    print(f"[build] Knowledge dir: {KNOWLEDGE_DIR}")
    if not KNOWLEDGE_DIR.exists():
        print("[build] ERROR: Knowledge/ folder missing.")
        return 1
    payload = build_index_payload(KNOWLEDGE_DIR)
    path = write_built_index(payload, BUILT_INDEX_FILE)
    print(
        f"[build] Wrote {path} — "
        f"{payload['documents_count']} docs, {payload['chunks_count']} chunks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
