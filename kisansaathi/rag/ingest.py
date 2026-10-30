"""Build the knowledge base: download official docs (sources.yaml) -> text per page -> chunks -> embeddings -> Chroma.

Run:  python -m kisansaathi.rag.ingest      (idempotent; re-downloads only missing files)
Chunks never cross page boundaries, so every retrieved passage has an exact page citation.
"""
from __future__ import annotations

import html
import re
import sys

import httpx
import yaml
from pypdf import PdfReader

from ..config import DATA_DIR, settings

RAW = DATA_DIR / "raw"
CHUNK, OVERLAP = 1200, 200  # characters (~250-300 tokens) — small enough to cite precisely
COLLECTION = "agri_docs"


def download(doc: dict) -> "Path":  # noqa: F821
    ext = "pdf" if doc["type"] == "pdf" else "htm"
    path = RAW / f"{doc['id']}.{ext}"
    if not path.exists() or path.stat().st_size < 1000:
        RAW.mkdir(parents=True, exist_ok=True)
        print(f"downloading {doc['id']} …", flush=True)
        r = httpx.get(doc["url"], timeout=180, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def pages(doc: dict, path) -> list[tuple[int, str]]:
    if doc["type"] == "pdf":
        return [(i, p.extract_text() or "") for i, p in enumerate(PdfReader(str(path)).pages, 1)]
    raw = path.read_text(encoding="latin-1")
    raw = re.sub(r"<(script|style).*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"</(tr|p|h\d|li|table)>", "\n", raw, flags=re.I)
    raw = re.sub(r"</t[dh]>", " | ", raw, flags=re.I)
    return [(1, html.unescape(re.sub(r"<[^>]+>", " ", raw)))]


def chunks(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if len(text) < 80:  # cover pages, blank pages, figure-only pages
        return []
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + CHUNK])
        i += CHUNK - OVERLAP
    return out


def get_collection():
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    client = chromadb.PersistentClient(path=str(settings().chroma_dir))
    ef = SentenceTransformerEmbeddingFunction(model_name=settings().embed_model)
    return client.get_or_create_collection(COLLECTION, embedding_function=ef, metadata={"hnsw:space": "cosine"})


def main() -> None:
    docs = yaml.safe_load((DATA_DIR / "sources.yaml").read_text())["documents"]
    col = get_collection()
    for doc in docs:
        try:
            path = download(doc)
        except Exception as e:  # one dead link must not kill the whole build
            print(f"!! skip {doc['id']}: {e}", file=sys.stderr)
            continue
        ids, texts, metas = [], [], []
        for page, text in pages(doc, path):
            for j, ch in enumerate(chunks(text)):
                ids.append(f"{doc['id']}:p{page}:c{j}")
                texts.append(ch)
                metas.append({"doc_id": doc["id"], "title": doc["title"], "publisher": doc["publisher"],
                              "url": doc["url"], "page": page, "crops": ",".join(doc["crops"])})
        for k in range(0, len(ids), 128):
            col.upsert(ids=ids[k:k + 128], documents=texts[k:k + 128], metadatas=metas[k:k + 128])
        print(f"{doc['id']}: {len(ids)} chunks", flush=True)
    print(f"total chunks in index: {col.count()}")


if __name__ == "__main__":
    main()
