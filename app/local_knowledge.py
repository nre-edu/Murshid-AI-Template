"""Local Markdown knowledge retrieval with build-time index support."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.arabic_text_fix import fix_arabic_pdf_text
from app.config import BASE_DIR, BUILT_INDEX_FILE, DATA_DIR, IS_SERVERLESS, KNOWLEDGE_DIR

ARABIC_STOP_WORDS = {
    "ما", "هي", "هو", "هم", "هن", "ماذا", "كيف", "اين", "متى", "لماذا", "هل",
    "وفقا", "وفق", "حسب", "بشان", "حول", "عن", "في", "من", "الى", "علي", "مع",
    "هذا", "هذه", "ذلك", "تلك", "كل", "جميع", "بعض", "اي", "التي", "الذي",
    "الذين", "اللواتي", "اللاتي", "المنوطه", "منوطه", "المنوط", "منوط", "كافة",
}

WEAK_ONLY_TERMS = {
    "دليل", "الدليل", "مصدر", "المصادر", "قسم", "القسم",
    "مهام", "مسؤوليات", "مسؤوليه", "التطبيقات", "المهام",
}

DOC_HINTS = [
    (("ذكاء اصطناعي", "الذكاء الاصطناعي", "تعلم الاله", "التعلم العميق", "توليدي"), "ai-demo-001"),
]


def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split()).lower()


def stem_arabic_word(word: str) -> List[str]:
    variants = [word]
    w = word
    if len(w) > 4 and (w.startswith("بال") or w.startswith("فال") or w.startswith("كال") or w.startswith("وال")):
        w = "ال" + w[3:]
        variants.append(w)
    elif len(w) > 4 and w.startswith("لل"):
        w = "ال" + w[2:]
        variants.append(w)
    elif len(w) > 3 and (w.startswith("و") or w.startswith("ف") or w.startswith("ب") or w.startswith("ل") or w.startswith("ك")):
        w = w[1:]
        variants.append(w)

    if w.startswith("ال") and len(w) > 3:
        w_bare = w[2:]
        variants.append(w_bare)
        if len(w_bare) > 3 and (w_bare.endswith("ها") or w_bare.endswith("هم") or w_bare.endswith("هن") or w_bare.endswith("كم") or w_bare.endswith("نا")):
            variants.append(w_bare[:-2])
        elif len(w_bare) > 3 and (w_bare.endswith("ات") or w_bare.endswith("ين") or w_bare.endswith("ون")):
            variants.append(w_bare[:-2])
    return list(dict.fromkeys(variants))


def tokenize(text: str, filter_stops: bool = True) -> List[str]:
    norm = normalize_arabic(text)
    raw_words = [w for w in norm.split() if len(w) >= 2]
    tokens = []
    for w in raw_words:
        if filter_stops and w in ARABIC_STOP_WORDS:
            continue
        tokens.extend(stem_arabic_word(w))
    return list(dict.fromkeys(tokens))


def detect_preferred_doc(norm_query: str) -> Optional[str]:
    for hints, doc_id in DOC_HINTS:
        for h in hints:
            if normalize_arabic(h) in norm_query or h in norm_query:
                return doc_id
    return None


def extract_key_phrases(norm_query: str) -> List[str]:
    raw_words = [w for w in norm_query.split() if len(w) >= 2 and w not in ARABIC_STOP_WORDS]
    phrases = []
    for i in range(len(raw_words) - 1):
        phrases.append(f"{raw_words[i]} {raw_words[i+1]}")
        if i + 2 < len(raw_words):
            phrases.append(f"{raw_words[i]} {raw_words[i+1]} {raw_words[i+2]}")
    for entity in (
        "الذكاء الاصطناعي",
        "تعلم الاله",
        "التعلم العميق",
        "التعلم الخاضع للاشراف",
        "الصيانه التنبؤيه",
        "الذكاء الاصطناعي التوليدي",
    ):
        if entity in norm_query:
            phrases.append(entity)
    return list(dict.fromkeys(p for p in phrases if len(p) > 5))


def is_indexable_knowledge_file(md_path: Path) -> bool:
    """
    Index all supported Markdown under Knowledge/, excluding:
    - any path under _examples/
    - underscore-prefixed filenames
    - test/demo question files by name
    """
    try:
        rel = md_path.resolve().relative_to(KNOWLEDGE_DIR.resolve())
    except ValueError:
        rel = md_path
    parts_lower = {p.lower() for p in Path(rel).parts}
    if "_examples" in parts_lower:
        return False
    if md_path.name.startswith("_"):
        return False
    name_l = md_path.name.lower()
    if "test-questions" in name_l or name_l.startswith("demo-questions") or "ai-demo-test" in name_l:
        return False
    return md_path.suffix.lower() in (".md", ".markdown")


def list_indexable_markdown_files(knowledge_dir: Path) -> List[Path]:
    if not knowledge_dir.exists():
        return []
    files = [p for p in knowledge_dir.rglob("*.md") if is_indexable_knowledge_file(p)]
    files += [p for p in knowledge_dir.rglob("*.markdown") if is_indexable_knowledge_file(p)]
    # Deduplicate by resolved path
    seen = set()
    out = []
    for p in sorted(files, key=lambda x: str(x).lower()):
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    meta: Dict[str, Any] = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1]
            body = parts[2]
            for line in raw_meta.splitlines():
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def chunk_document(doc_id: str, doc_title: str, orig_name: str, body: str) -> List[Dict[str, Any]]:
    lines = body.split("\n")
    raw_sections = []
    current_h1 = doc_title
    current_h2 = ""
    current_h3 = ""
    current_lines: List[str] = []
    current_page = None
    parent_unit = ""

    def flush():
        nonlocal current_lines
        text_content = "\n".join(current_lines).strip()
        if len(text_content) > 15:
            sec_parts = [p for p in [current_h2, current_h3] if p]
            sec_title = " - ".join(sec_parts) if sec_parts else current_h1
            raw_sections.append({
                "section_title": sec_title,
                "page": current_page,
                "content": text_content,
                "parent_unit": parent_unit,
            })
        current_lines = []

    for line in lines:
        line_str = line.strip()
        p_match = re.search(r"<!-- Page (\d+) -->", line)
        if p_match:
            current_page = int(p_match.group(1))

        h1_match = re.match(r"^#\s+(.+)$", line_str)
        h2_match = re.match(r"^##\s+(.+)$", line_str)
        h3_match = re.match(r"^###\s+(.+)$", line_str)

        if h1_match or h2_match or h3_match:
            flush()
            if h1_match:
                current_h1 = h1_match.group(1).strip()
                current_h2 = ""
                current_h3 = ""
                parent_unit = ""
            elif h2_match:
                current_h2 = h2_match.group(1).strip()
                current_h3 = ""
                parent_unit = current_h2
            elif h3_match:
                current_h3 = h3_match.group(1).strip()
                parent_unit = current_h3
        else:
            current_lines.append(line)
    flush()

    final_chunks: List[Dict[str, Any]] = []
    chunk_counter = 0
    for sec in raw_sections:
        content = sec["content"]
        sec_title = sec["section_title"]
        page = sec["page"]
        unit = sec.get("parent_unit") or ""
        prefix = f"{unit}\n\n" if unit and unit not in content[:80] else ""

        if len(content) <= 1200:
            chunk_counter += 1
            joined = prefix + content if prefix and not content.startswith(unit) else content
            final_chunks.append({
                "chunk_id": f"{doc_id}_c{chunk_counter}",
                "doc_id": doc_id,
                "doc_title": doc_title,
                "original_filename": orig_name,
                "section_title": sec_title,
                "parent_unit": unit,
                "page": page,
                "content": joined,
                "char_count": len(joined),
            })
        else:
            paragraphs = content.split("\n\n")
            sub_block: List[str] = []
            sub_len = 0
            part_idx = 1
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                if sub_len + len(p) > 900 and sub_block:
                    chunk_counter += 1
                    joined = "\n\n".join(sub_block)
                    if prefix and not joined.startswith(unit):
                        joined = prefix + joined
                    final_chunks.append({
                        "chunk_id": f"{doc_id}_c{chunk_counter}",
                        "doc_id": doc_id,
                        "doc_title": doc_title,
                        "original_filename": orig_name,
                        "section_title": f"{sec_title} (جزء {part_idx})",
                        "parent_unit": unit,
                        "page": page,
                        "content": joined,
                        "char_count": len(joined),
                    })
                    sub_block = [p]
                    sub_len = len(p)
                    part_idx += 1
                else:
                    sub_block.append(p)
                    sub_len += len(p)
            if sub_block:
                chunk_counter += 1
                joined = "\n\n".join(sub_block)
                if prefix and not joined.startswith(unit):
                    joined = prefix + joined
                final_chunks.append({
                    "chunk_id": f"{doc_id}_c{chunk_counter}",
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "original_filename": orig_name,
                    "section_title": f"{sec_title} (جزء {part_idx})" if part_idx > 1 else sec_title,
                    "parent_unit": unit,
                    "page": page,
                    "content": joined,
                    "char_count": len(joined),
                })
    return final_chunks


def build_index_payload(knowledge_dir: Path = None) -> Dict[str, Any]:
    """Build a JSON-serializable BM25 index from Knowledge Markdown files."""
    kdir = knowledge_dir or KNOWLEDGE_DIR
    md_files = list_indexable_markdown_files(kdir)
    docs_dict: Dict[str, Any] = {}
    all_chunks: List[Dict[str, Any]] = []

    for md_path in md_files:
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = fix_arabic_pdf_text(content)
            meta, body = parse_frontmatter(content)
            doc_id = meta.get("id") or md_path.stem
            doc_title = meta.get("title") or md_path.stem.replace("_", " ")
            orig_file = meta.get("original_filename") or md_path.name
            try:
                rel_path = str(md_path.resolve().relative_to(BASE_DIR.resolve()))
            except ValueError:
                rel_path = str(md_path)
            doc_chunks = chunk_document(doc_id, doc_title, orig_file, body)
            all_chunks.extend(doc_chunks)
            docs_dict[doc_id] = {
                "id": doc_id,
                "title": doc_title,
                "original_filename": orig_file,
                "release_date": meta.get("release_date") or meta.get("prepared_on") or "",
                "version": meta.get("version") or "",
                "file_path": rel_path.replace("\\", "/"),
                "file_size": md_path.stat().st_size,
                "sections_count": len(doc_chunks),
            }
        except Exception as e:
            print(f"[KnowledgeEngine] Error parsing {md_path.name}: {e}")

    N = len(all_chunks)
    inverted: Dict[str, List[List[int]]] = {}
    doc_lengths: List[int] = []
    total_len = 0
    doc_chunk_indices: Dict[str, List[int]] = {}

    for idx, chunk in enumerate(all_chunks):
        full_text = (
            f"{chunk['doc_title']} {chunk['section_title']} "
            f"{chunk.get('parent_unit', '')} {chunk['section_title']} {chunk['content']}"
        )
        tokens = tokenize(full_text, filter_stops=True)
        doc_len = len(tokens)
        doc_lengths.append(doc_len)
        total_len += doc_len
        doc_chunk_indices.setdefault(chunk["doc_id"], []).append(idx)
        term_counts: Dict[str, int] = {}
        for t in tokens:
            term_counts[t] = term_counts.get(t, 0) + 1
        for t, count in term_counts.items():
            inverted.setdefault(t, []).append([idx, count])

    avg_dl = (total_len / N) if N > 0 else 1.0
    idf = {}
    for t, postings in inverted.items():
        df = len(postings)
        idf[t] = math.log(1.0 + (N - df + 0.5) / (df + 0.5))

    return {
        "version": 1,
        "last_indexed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "knowledge_path": "Knowledge",
        "documents_count": len(docs_dict),
        "chunks_count": len(all_chunks),
        "documents": docs_dict,
        "chunks": all_chunks,
        "doc_lengths": doc_lengths,
        "avg_doc_len": avg_dl,
        "inverted_index": inverted,
        "idf": idf,
        "doc_chunk_indices": doc_chunk_indices,
    }


def write_built_index(payload: Dict[str, Any], dest: Path = None) -> Path:
    path = dest or BUILT_INDEX_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    # Lightweight status sidecar (safe to commit or ignore)
    status = {
        "last_indexed": payload.get("last_indexed"),
        "documents_count": payload.get("documents_count"),
        "chunks_count": payload.get("chunks_count"),
        "source": "build_time",
    }
    with open(DATA_DIR / "local_index.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    return path


class LocalKnowledgeEngine:
    def __init__(self):
        self.knowledge_dir = KNOWLEDGE_DIR
        self.built_index_file = BUILT_INDEX_FILE
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.chunks: List[Dict[str, Any]] = []
        self.chunk_by_id: Dict[str, Dict[str, Any]] = {}
        self.doc_chunk_indices: Dict[str, List[int]] = {}
        self.doc_lengths: List[int] = []
        self.avg_doc_len: float = 0.0
        self.inverted_index: Dict[str, List[Tuple[int, int]]] = {}
        self.idf: Dict[str, float] = {}
        self.last_indexed_time: Optional[str] = None
        self._dir_mtime: float = 0.0
        self._loaded_from_built = False
        self.load_or_build()

    def _get_dir_state(self) -> float:
        if not self.knowledge_dir.exists():
            return 0.0
        max_m = 0.0
        for f in list_indexable_markdown_files(self.knowledge_dir):
            try:
                max_m = max(max_m, f.stat().st_mtime)
            except Exception:
                pass
        return max_m

    def _apply_payload(self, payload: Dict[str, Any]):
        self.documents = payload.get("documents") or {}
        self.chunks = payload.get("chunks") or []
        self.chunk_by_id = {c["chunk_id"]: c for c in self.chunks}
        self.doc_chunk_indices = payload.get("doc_chunk_indices") or {}
        self.doc_lengths = payload.get("doc_lengths") or []
        self.avg_doc_len = float(payload.get("avg_doc_len") or 1.0)
        raw_inv = payload.get("inverted_index") or {}
        self.inverted_index = {
            t: [(int(pair[0]), int(pair[1])) for pair in postings]
            for t, postings in raw_inv.items()
        }
        self.idf = {k: float(v) for k, v in (payload.get("idf") or {}).items()}
        self.last_indexed_time = payload.get("last_indexed")
        self._dir_mtime = self._get_dir_state()

    def load_built_index(self) -> bool:
        if not self.built_index_file.exists():
            return False
        try:
            with open(self.built_index_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not payload.get("chunks"):
                return False
            self._apply_payload(payload)
            self._loaded_from_built = True
            print(
                f"[KnowledgeEngine] Loaded built index: "
                f"{len(self.documents)} docs / {len(self.chunks)} chunks"
            )
            return True
        except Exception as e:
            print(f"[KnowledgeEngine] Failed to load built index: {e}")
            return False

    def rebuild_index(self, persist: bool = None) -> Dict[str, Any]:
        """Rebuild from Knowledge/. Persist to disk unless serverless/read-only."""
        if persist is None:
            persist = not IS_SERVERLESS
        payload = build_index_payload(self.knowledge_dir)
        self._apply_payload(payload)
        self._loaded_from_built = False
        if persist:
            try:
                write_built_index(payload, self.built_index_file)
            except Exception as e:
                print(f"[KnowledgeEngine] Could not write index (read-only FS?): {e}")
        print(
            f"[KnowledgeEngine] Indexed {len(self.documents)} documents "
            f"into {len(self.chunks)} sections."
        )
        return payload

    def load_or_build(self):
        # Prefer prebuilt index (Vercel / production). Rebuild locally if missing or stale.
        loaded = self.load_built_index()
        if IS_SERVERLESS:
            if not loaded:
                # Last resort on serverless: build in-memory only (no write)
                self.rebuild_index(persist=False)
            return

        if not loaded:
            self.rebuild_index(persist=True)
            return

        # Local: refresh if Knowledge files changed after index
        current = self._get_dir_state()
        md_count = len(list_indexable_markdown_files(self.knowledge_dir))
        if current > self._dir_mtime or len(self.documents) != md_count:
            self.rebuild_index(persist=True)

    def check_and_reload_if_needed(self):
        if IS_SERVERLESS:
            return
        current = self._get_dir_state()
        md_count = len(list_indexable_markdown_files(self.knowledge_dir))
        if current > self._dir_mtime or len(self.documents) != md_count:
            self.rebuild_index(persist=True)

    def get_status(self) -> Dict[str, Any]:
        self.check_and_reload_if_needed()
        return {
            "source_type": "local_markdown",
            "storage_path": "Knowledge/",
            "documents_count": len(self.documents),
            "chunks_count": len(self.chunks),
            "last_indexed": self.last_indexed_time,
            "ready": len(self.chunks) > 0,
            "readonly": IS_SERVERLESS,
            "index_source": "built" if self._loaded_from_built else "live",
        }

    def get_documents_list(self) -> List[Dict[str, Any]]:
        self.check_and_reload_if_needed()
        # Do not leak absolute server paths to clients
        safe = []
        for doc in self.documents.values():
            item = dict(doc)
            fp = item.get("file_path", "")
            if fp and (":" in fp or fp.startswith("/") or "\\" in fp):
                item["file_path"] = Path(fp).name
            safe.append(item)
        return safe

    def get_source_section(self, doc_id: str, chunk_id: str) -> Optional[Dict[str, Any]]:
        self.check_and_reload_if_needed()
        chunk = self.chunk_by_id.get(chunk_id)
        if not chunk or chunk.get("doc_id") != doc_id:
            return None
        doc = self.documents.get(doc_id, {})
        return {
            "doc_id": doc_id,
            "doc_title": chunk.get("doc_title", ""),
            "original_filename": chunk.get("original_filename", ""),
            "release_date": doc.get("release_date", ""),
            "version": doc.get("version", ""),
            "section_title": chunk.get("section_title", ""),
            "page": chunk.get("page"),
            "content": chunk.get("content", ""),
            "char_count": chunk.get("char_count", 0),
        }

    def _topical_overlap_ok(self, query_tokens: List[str], chunk: Dict[str, Any], phrases: List[str]) -> bool:
        norm_content = normalize_arabic(
            f"{chunk.get('section_title', '')} {chunk.get('parent_unit', '')} {chunk['content']}"
        )
        strong_hits = 0
        phrase_hit = False
        for t in query_tokens:
            if t in WEAK_ONLY_TERMS or t in ARABIC_STOP_WORDS or len(t) < 4:
                continue
            if t in norm_content:
                strong_hits += 1
        for ph in phrases:
            if len(ph) > 6 and ph in norm_content:
                strong_hits += 3
                phrase_hit = True
        if phrases:
            return phrase_hit or strong_hits >= 3
        return strong_hits >= 2

    def search_bm25(self, query: str, top_k: int = 8) -> List[Tuple[float, Dict[str, Any]]]:
        self.check_and_reload_if_needed()
        if not self.chunks:
            return []

        query_tokens = tokenize(query, filter_stops=True)
        if not query_tokens:
            query_tokens = tokenize(query, filter_stops=False)
            if not query_tokens:
                return []

        norm_query = normalize_arabic(query)
        scores: Dict[int, float] = {}
        k1 = 1.5
        b = 0.75

        for term in query_tokens:
            if term not in self.inverted_index:
                continue
            term_idf = self.idf.get(term, 0.0)
            for chunk_idx, tf in self.inverted_index[term]:
                dl = self.doc_lengths[chunk_idx] if chunk_idx < len(self.doc_lengths) else 1
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (dl / self.avg_doc_len))
                scores[chunk_idx] = scores.get(chunk_idx, 0.0) + term_idf * (numerator / denominator)

        phrases = extract_key_phrases(norm_query)
        preferred_doc_id = detect_preferred_doc(norm_query)

        for chunk_idx in list(scores.keys()):
            chunk = self.chunks[chunk_idx]
            norm_content = normalize_arabic(chunk["content"])
            norm_sec = normalize_arabic(f"{chunk.get('parent_unit', '')} {chunk['section_title']}")
            for ph in phrases:
                if ph in norm_sec:
                    scores[chunk_idx] += 45.0
                elif ph in norm_content:
                    scores[chunk_idx] += 30.0
            if preferred_doc_id:
                if chunk["doc_id"] == preferred_doc_id:
                    scores[chunk_idx] += 25.0
                else:
                    scores[chunk_idx] *= 0.35
            if not self._topical_overlap_ok(query_tokens, chunk, phrases):
                scores[chunk_idx] *= 0.15

        scored_list = [(score, self.chunks[idx]) for idx, score in scores.items() if score > 0]
        scored_list.sort(key=lambda x: x[0], reverse=True)
        return scored_list[:top_k]

    def _expand_neighbors(self, scored: List[Tuple[float, Dict[str, Any]]], limit: int):
        if not scored:
            return scored
        chosen = list(scored)
        seen = {c["chunk_id"] for _, c in chosen}
        for score, chunk in scored[:3]:
            unit = (chunk.get("parent_unit") or "").strip()
            doc_id = chunk["doc_id"]
            indices = self.doc_chunk_indices.get(doc_id, [])
            try:
                pos = next(i for i in indices if self.chunks[i]["chunk_id"] == chunk["chunk_id"])
            except StopIteration:
                continue
            for neighbor_pos in (pos - 1, pos + 1):
                if neighbor_pos < 0 or neighbor_pos >= len(self.chunks):
                    continue
                nb = self.chunks[neighbor_pos]
                if nb["doc_id"] != doc_id or nb["chunk_id"] in seen:
                    continue
                nb_unit = (nb.get("parent_unit") or "").strip()
                related = False
                if unit and nb_unit == unit:
                    related = True
                elif unit and normalize_arabic(unit) in normalize_arabic(nb["content"] + " " + nb["section_title"]):
                    related = True
                if related:
                    chosen.append((score * 0.85, nb))
                    seen.add(nb["chunk_id"])
                if len(chosen) >= limit:
                    break
            if len(chosen) >= limit:
                break
        chosen.sort(key=lambda x: x[0], reverse=True)
        out = []
        seen2 = set()
        for s, c in chosen:
            if c["chunk_id"] in seen2:
                continue
            seen2.add(c["chunk_id"])
            out.append((s, c))
        return out[:limit]

    def retrieve_for_chat(self, query: str, top_k: int = 4) -> Tuple[List[Dict[str, Any]], str, bool]:
        scored_results = self.search_bm25(query, top_k=max(top_k, 6))
        scored_results = self._expand_neighbors(scored_results, limit=top_k + 2)
        if not scored_results:
            return [], "", False

        top_score, top_chunk = scored_results[0]
        phrases = extract_key_phrases(normalize_arabic(query))
        q_tokens = tokenize(query, filter_stops=True)
        # Slightly lower gate for small demo corpora
        min_score = 8.0 if len(self.chunks) <= 20 else 12.0
        if top_score < min_score or not self._topical_overlap_ok(q_tokens, top_chunk, phrases):
            return [], "", False

        entity_phrases = [p for p in phrases if len(p) >= 9]
        phrase_hit_units = set()
        if entity_phrases:
            for score, chunk in scored_results:
                blob = normalize_arabic(
                    f"{chunk.get('parent_unit', '')} {chunk['section_title']} {chunk['content']}"
                )
                if any(p in blob for p in entity_phrases):
                    u = (chunk.get("parent_unit") or "").strip()
                    if u:
                        phrase_hit_units.add(u)

        filtered = []
        for score, chunk in scored_results:
            if score < max(min_score * 0.8, top_score * 0.25):
                continue
            if not self._topical_overlap_ok(q_tokens, chunk, phrases):
                continue
            if entity_phrases:
                blob = normalize_arabic(
                    f"{chunk.get('parent_unit', '')} {chunk['section_title']} {chunk['content']}"
                )
                unit = (chunk.get("parent_unit") or "").strip()
                has_entity = any(p in blob for p in entity_phrases)
                same_unit = unit and unit in phrase_hit_units
                if not has_entity and not same_unit:
                    continue
            filtered.append((score, chunk))
            if len(filtered) >= top_k:
                break
        if not filtered:
            return [], "", False

        citations = []
        context_blocks = []
        for rank, (score, chunk) in enumerate(filtered, 1):
            content_snippet = chunk["content"].strip()
            first_lines = [
                l.strip()
                for l in content_snippet.split("\n")
                if l.strip() and not l.startswith("<!--")
            ][:5]
            excerpt = " ".join(first_lines)
            if len(excerpt) > 280:
                excerpt = excerpt[:280] + "..."
            citations.append({
                "citation_id": rank,
                "doc_id": chunk["doc_id"],
                "doc_title": chunk["doc_title"],
                "section_title": chunk["section_title"],
                "original_filename": chunk["original_filename"],
                "chunk_id": chunk["chunk_id"],
                "page": chunk.get("page"),
                "excerpt": excerpt,
                "relevance_score": round(score, 2),
            })
            page_text = f" (صفحة {chunk['page']})" if chunk.get("page") else ""
            header = (
                f"[المصدر {rank} | الدليل: {chunk['doc_title']}{page_text} "
                f"| القسم: {chunk['section_title']} | chunk_id: {chunk['chunk_id']}]"
            )
            context_blocks.append(f"{header}\n{content_snippet}")

        return citations, "\n\n---\n\n".join(context_blocks), True


local_knowledge = LocalKnowledgeEngine()
