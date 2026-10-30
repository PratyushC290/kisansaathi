"""Retrieve passages from official crop guides.

Hybrid search: multilingual embeddings (Chroma) catch meaning across languages; BM25 keywords catch exact
technical terms ("thrips", "late blight") that small embedding models blur. Ranks are merged with
reciprocal-rank fusion, then passages from the crop's own guide get a small boost.
"""
from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache

from ..models import ToolResult

RRF_K = 60
CROP_BOOST = 1.25
TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in on for and or is are be with at by from as it this that what when how should i my "
           "do does can which crop".split())


def _tok(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@lru_cache
def _collection():
    from ..rag.ingest import get_collection
    return get_collection()


@lru_cache
def _bm25():
    from rank_bm25 import BM25Okapi
    got = _collection().get(include=["documents", "metadatas"])
    return BM25Okapi([_tok(d) for d in got["documents"]]), got["ids"], got["documents"], got["metadatas"]


def retrieve(query: str, crop: str | None = None, k: int = 4, query_en: str | None = None) -> ToolResult:
    """`query` may be in any language; pass `query_en` too when available (keyword search is English)."""
    try:
        col = _collection()
        if col.count() == 0:
            return ToolResult(tool="knowledge", ok=False, source="Official crop guides",
                              error="knowledge base is empty — run python -m kisansaathi.rag.ingest")
        q_en = query_en or query
        q_vec = f"{crop} {q_en}" if crop and crop not in q_en.lower() else q_en
        scores: dict[str, float] = {}
        info: dict[str, tuple[str, dict]] = {}

        res = col.query(query_texts=[q_vec], n_results=30)
        for rank, (cid, doc, meta) in enumerate(zip(res["ids"][0], res["documents"][0], res["metadatas"][0], strict=True)):
            scores[cid] = scores.get(cid, 0) + 1 / (RRF_K + rank)
            info[cid] = (doc, meta)

        bm25, ids, docs, metas = _bm25()
        toks = _tok(q_vec)
        if toks:
            bm = bm25.get_scores(toks)
            top = sorted(range(len(ids)), key=lambda i: -bm[i])[:30]
            for rank, i in enumerate(top):
                if bm[i] <= 0:
                    break
                scores[ids[i]] = scores.get(ids[i], 0) + 1 / (RRF_K + rank)
                info[ids[i]] = (docs[i], metas[i])

        hits = []
        for cid, s in scores.items():
            doc, meta = info[cid]
            if crop and crop in meta["crops"].split(","):
                s *= CROP_BOOST
            hits.append({"chunk_id": cid, "text": doc.strip(), "doc_id": meta["doc_id"], "title": meta["title"],
                         "publisher": meta["publisher"], "url": meta["url"], "page": meta["page"],
                         "score": round(s * 100, 2)})
        hits.sort(key=lambda h: -h["score"])
        if crop:  # the crop's own guides first; other docs only fill remaining slots
            own = [h for h in hits if crop in info[h["chunk_id"]][1]["crops"].split(",")]
            hits = own + [h for h in hits if h not in own]
        # avoid returning three overlapping chunks of the same page
        seen, out = set(), []
        for h in hits:
            key = (h["doc_id"], h["page"])
            if key not in seen:
                seen.add(key)
                out.append(h)
            if len(out) == k:
                break
        return ToolResult(tool="knowledge", ok=True, data=out, source="Official crop guides (PAU, ICAR, FAO)",
                          fetched_at=datetime.now())
    except Exception as e:  # noqa: BLE001
        return ToolResult(tool="knowledge", ok=False, source="Official crop guides", error=f"{type(e).__name__}: {e}")
