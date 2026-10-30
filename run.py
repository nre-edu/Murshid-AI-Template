import sys
import os
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

if __name__ == "__main__":
    try:
        from app.local_knowledge import build_index_payload, write_built_index
        from app.config import BUILT_INDEX_FILE, KNOWLEDGE_DIR

        payload = build_index_payload(KNOWLEDGE_DIR)
        write_built_index(payload, BUILT_INDEX_FILE)
        print(
            f"[Daleel] Index ready: {payload['documents_count']} docs / "
            f"{payload['chunks_count']} chunks"
        )
    except Exception as ex:
        print(f"[Daleel] Index build skipped/failed: {ex}")

    print("=" * 60)
    print("Daleel Server - Starting...")
    print("URL: http://127.0.0.1:8000")
    print("Knowledge: ./Knowledge (server-side only)")
    print("=" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
