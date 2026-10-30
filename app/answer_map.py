"""
Server-side validation for Answer Map (خريطة الإجابة).
Only validated maps bound to real retrieved chunk ids are returned to the client.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

MAX_NODES = 10
MAX_EDGES = 12
MAX_BRANCHES = 4
MAX_DEPTH = 2
MAX_LABEL_LEN = 72

# Illustrative DEMO map aligned with the bundled AI demo knowledge domain.
# Marked isDemo=true — never mixed into live retrieval answers.
DEMO_ANSWER_MAP: Dict[str, Any] = {
    "isDemo": True,
    "rootId": "ai",
    "nodes": [
        {"id": "ai", "label": "الذكاء الاصطناعي", "detail": "موضوع السؤال (عينة توضيحية)", "sourceIds": []},
        {"id": "def", "label": "التعريف", "detail": "تقنيات تمكّن الحواسيب من التعلم وفهم اللغة وحل المشكلات", "sourceIds": ["demo-1"]},
        {"id": "ml", "label": "تعلم الآلة", "detail": "فرع يتعلم أنماطًا من البيانات", "sourceIds": ["demo-2"]},
        {"id": "dl", "label": "التعلم العميق", "detail": "فرع من تعلم الآلة بشبكات عصبية متعددة الطبقات", "sourceIds": ["demo-2"]},
        {"id": "apps", "label": "تطبيقات عملية", "detail": "أمثلة واردة في الدليل التجريبي", "sourceIds": ["demo-3"]},
        {"id": "support", "label": "خدمة العملاء", "detail": "الرد على الاستفسارات المتكررة", "sourceIds": ["demo-3"]},
        {"id": "predict", "label": "الصيانة التنبؤية", "detail": "توقع أعطال المعدات من بيانات المستشعرات", "sourceIds": ["demo-3"]},
    ],
    "edges": [
        {"from": "ai", "to": "def", "label": "يُعرَّف بأنه", "sourceIds": ["demo-1"]},
        {"from": "ai", "to": "ml", "label": "يشمل", "sourceIds": ["demo-2"]},
        {"from": "ml", "to": "dl", "label": "ومن فروعه", "sourceIds": ["demo-2"]},
        {"from": "ai", "to": "apps", "label": "من تطبيقاته", "sourceIds": ["demo-3"]},
        {"from": "apps", "to": "support", "label": "", "sourceIds": ["demo-3"]},
        {"from": "apps", "to": "predict", "label": "", "sourceIds": ["demo-3"]},
    ],
    "sources": [
        {"id": "demo-1", "title": "مصدر تجريبي 1", "excerpt": "الذكاء الاصطناعي تقنيات تمكّن الحواسيب من أداء مهام مثل التعلم وفهم اللغة وحل المشكلات واتخاذ القرارات."},
        {"id": "demo-2", "title": "مصدر تجريبي 2", "excerpt": "تعلم الآلة فرع من الذكاء الاصطناعي. التعلم العميق فرع من تعلم الآلة يستخدم شبكات عصبية متعددة الطبقات."},
        {"id": "demo-3", "title": "مصدر تجريبي 3", "excerpt": "من التطبيقات العملية: خدمة العملاء، كشف الاحتيال، والصيانة التنبؤية لتوقع أعطال المعدات."},
    ],
}

DEMO_ANSWER_TEXT = (
    "الإجابة: **الذكاء الاصطناعي** تقنيات تمكّن الحواسيب من التعلم وفهم اللغة وحل المشكلات [1]. "
    "و**تعلم الآلة** فرع منه، بينما **التعلم العميق** فرع من تعلم الآلة يعتمد شبكات عصبية متعددة الطبقات [2]. "
    "ومن التطبيقات العملية الواردة في الدليل: **خدمة العملاء** و**الصيانة التنبؤية** [3]."
)


def _as_str_list(val: Any) -> List[str]:
    if not isinstance(val, list):
        return []
    out = []
    for x in val:
        if isinstance(x, (str, int)):
            s = str(x).strip()
            if s:
                out.append(s)
    return out


def _node_depth(root_id: str, edges: List[Dict[str, str]], node_id: str) -> int:
    # BFS parents
    parents: Dict[str, List[str]] = {}
    for e in edges:
        parents.setdefault(e["to"], []).append(e["from"])
    if node_id == root_id:
        return 0
    visited = set()
    stack = [(node_id, 0)]
    while stack:
        cur, d = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        for p in parents.get(cur, []):
            if p == root_id:
                return d + 1
            stack.append((p, d + 1))
    return 99


def validate_answer_map(
    raw_map: Any,
    allowed_chunk_ids: Set[str],
    citations: List[Dict[str, Any]],
    *,
    allow_demo: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Validate and normalize answer map. Returns None if invalid.
    For real maps, every evidence sourceId must be in allowed_chunk_ids
    (or citation_id as string of rank — remapped to chunk_id).
    """
    if not isinstance(raw_map, dict):
        return None

    is_demo = bool(raw_map.get("isDemo"))
    if is_demo and not allow_demo:
        return None

    root_id = str(raw_map.get("rootId") or "").strip()
    nodes_in = raw_map.get("nodes")
    edges_in = raw_map.get("edges")
    if not root_id or not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        return None
    if not (1 <= len(nodes_in) <= MAX_NODES) or not (1 <= len(edges_in) <= MAX_EDGES):
        return None

    # citation rank -> chunk_id
    rank_to_chunk: Dict[str, str] = {}
    chunk_meta: Dict[str, Dict[str, Any]] = {}
    for c in citations or []:
        cid = str(c.get("chunk_id") or "")
        rank = str(c.get("citation_id") or "")
        if cid:
            chunk_meta[cid] = c
            allowed_chunk_ids.add(cid)
        if rank:
            rank_to_chunk[rank] = cid
            rank_to_chunk[f"[{rank}]"] = cid

    def resolve_sources(ids: List[str]) -> Optional[List[str]]:
        if is_demo and allow_demo:
            return ids
        resolved = []
        for sid in ids:
            if sid in allowed_chunk_ids:
                resolved.append(sid)
            elif sid in rank_to_chunk and rank_to_chunk[sid]:
                resolved.append(rank_to_chunk[sid])
            elif sid.startswith("demo-"):
                return None  # demo ids not allowed in live maps
            else:
                return None
        return resolved

    nodes: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()
    for n in nodes_in:
        if not isinstance(n, dict):
            return None
        nid = str(n.get("id") or "").strip()
        label = str(n.get("label") or "").strip()
        if not nid or not label or len(label) > MAX_LABEL_LEN:
            return None
        if nid in node_ids:
            return None
        src = resolve_sources(_as_str_list(n.get("sourceIds")))
        if src is None:
            return None
        # Root may have empty sources; others should have evidence when not demo
        if nid != root_id and not src and not (is_demo and allow_demo):
            return None
        node_ids.add(nid)
        nodes.append({
            "id": nid,
            "label": label,
            "detail": str(n.get("detail") or label)[:400],
            "sourceIds": src,
        })

    if root_id not in node_ids:
        return None

    edges: List[Dict[str, Any]] = []
    children_of_root = 0
    for e in edges_in:
        if not isinstance(e, dict):
            return None
        frm = str(e.get("from") or "").strip()
        to = str(e.get("to") or "").strip()
        if frm not in node_ids or to not in node_ids or frm == to:
            return None
        src = resolve_sources(_as_str_list(e.get("sourceIds")))
        if src is None or (not src and not (is_demo and allow_demo)):
            return None
        if frm == root_id:
            children_of_root += 1
        edges.append({
            "from": frm,
            "to": to,
            "label": str(e.get("label") or "")[:40],
            "sourceIds": src,
        })

    if children_of_root < 1 or children_of_root > MAX_BRANCHES:
        return None

    # Depth check
    for n in nodes:
        if n["id"] == root_id:
            continue
        d = _node_depth(root_id, edges, n["id"])
        if d > MAX_DEPTH:
            return None

    # Build sources panel from citations / demo sources
    sources_out: List[Dict[str, Any]] = []
    if is_demo and allow_demo:
        for s in raw_map.get("sources") or DEMO_ANSWER_MAP["sources"]:
            if isinstance(s, dict) and s.get("id"):
                sources_out.append({
                    "id": str(s["id"]),
                    "title": str(s.get("title") or "مصدر تجريبي"),
                    "excerpt": str(s.get("excerpt") or "")[:400],
                })
    else:
        used: Set[str] = set()
        for n in nodes:
            used.update(n["sourceIds"])
        for e in edges:
            used.update(e["sourceIds"])
        for cid in used:
            meta = chunk_meta.get(cid, {})
            sources_out.append({
                "id": cid,
                "title": meta.get("doc_title") or meta.get("section_title") or cid,
                "section_title": meta.get("section_title") or "",
                "excerpt": meta.get("excerpt") or "",
                "doc_id": meta.get("doc_id") or "",
                "chunk_id": cid,
                "citation_id": meta.get("citation_id"),
            })

    return {
        "isDemo": bool(is_demo and allow_demo),
        "rootId": root_id,
        "nodes": nodes,
        "edges": edges,
        "sources": sources_out,
    }
