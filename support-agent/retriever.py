"""
retriever.py — TF-IDF knowledge-base retrieval using scikit-learn.

Loads .md / .txt files from knowledge_base/, splits them into chunks,
builds a TfidfVectorizer index, and returns the top-k most relevant
chunks for a given query (filtered by min_retrieval_score).
"""

import os
import re
import yaml
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Config ────────────────────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "business_rules.yaml")

def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ── Document loading & chunking ───────────────────────────────────────────────
def _split_into_chunks(text: str, max_words: int = 250) -> list[str]:
    """
    Split text into coherent chunks by section or paragraph.
    Attaches markdown headings to their following body text so chunks
    remain self-contained and headings don't occupy isolated slots.
    If a section exceeds max_words, split it further by sentence.
    """
    if re.search(r"\n##?\s+", text):
        raw_sections = [s.strip() for s in re.split(r"\n(?=##?\s+)", text) if s.strip()]
    else:
        raw_sections = [s.strip() for s in re.split(r"\n{2,}", text) if s.strip()]

    chunks = []
    title_prefix = ""

    for section in raw_sections:
        section = section.strip()
        if not section:
            continue
        # If it's a top-level document title (# Title) with no body, keep it as prefix for the next section
        if section.startswith("# ") and "\n" not in section:
            title_prefix = section
            continue
        if title_prefix:
            section = f"{title_prefix}\n\n{section}"
            title_prefix = ""

        words = section.split()
        if len(words) <= max_words:
            chunks.append(section)
        else:
            # Break oversized sections into sentence-level pieces
            sentences = re.split(r"(?<=[.!?])\s+", section)
            current, count = [], 0
            for sent in sentences:
                w = len(sent.split())
                if count + w > max_words and current:
                    chunks.append(" ".join(current))
                    current, count = [sent], w
                else:
                    current.append(sent)
                    count += w
            if current:
                chunks.append(" ".join(current))

    return chunks


def load_documents(folder: str) -> list[dict]:
    """
    Read every .md and .txt file in `folder`.
    Returns a flat list of {source, text} dicts — one entry per chunk.
    """
    docs = []
    for fname in os.listdir(folder):
        if not fname.endswith((".md", ".txt")):
            continue
        path = os.path.join(folder, fname)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        for chunk in _split_into_chunks(raw):
            docs.append({"source": fname, "text": chunk})
    return docs

# ── Index ─────────────────────────────────────────────────────────────────────
class Retriever:
    def __init__(self, folder: str):
        self.folder = folder
        config = _load_config()
        self.min_score: float = config.get("min_retrieval_score", 0.1)
        self._build()

    def _build(self) -> None:
        """(Re)build the TF-IDF index from the current files in self.folder."""
        self.docs = load_documents(self.folder)
        if not self.docs:
            raise ValueError(f"No documents found in {self.folder!r}")
        texts = [d["text"] for d in self.docs]
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(texts)  # shape: (n_chunks, vocab)

    def rebuild(self) -> None:
        """Public method — call after adding files to the knowledge base folder."""
        self._build()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Return up to top_k chunks most similar to `query`.
        Each result: {source, text, score}. Drops results below min_score.
        """
        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix).flatten()

        # Get indices sorted by descending score
        ranked = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in ranked:
            score = float(scores[idx])
            if score < self.min_score:
                break                          # remaining scores are even lower
            results.append({
                "source": self.docs[idx]["source"],
                "text":   self.docs[idx]["text"],
                "score":  round(score, 4),
            })
        return results


# ── Module-level singleton with mtime-based cache invalidation ─────────────────
_cached_retriever: Retriever | None = None
_cached_mtime: float = 0.0


def get_retriever(folder: str) -> Retriever:
    """
    Return a cached Retriever, rebuilding the index automatically when any
    file inside `folder` has been added or modified since the last build.
    This lets app.py get a fresh index immediately after an upload.
    """
    global _cached_retriever, _cached_mtime

    # Compute the latest modification time across all files in the folder
    current_mtime = max(
        (os.path.getmtime(os.path.join(folder, f)) for f in os.listdir(folder)),
        default=0.0,
    )

    if _cached_retriever is None or current_mtime > _cached_mtime:
        if _cached_retriever is None:
            _cached_retriever = Retriever(folder)
        else:
            _cached_retriever.rebuild()        # re-fit on updated file set
        _cached_mtime = current_mtime

    return _cached_retriever

# ── Quick smoke-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    KB_FOLDER = os.path.join(os.path.dirname(__file__), "knowledge_base")
    r = Retriever(KB_FOLDER)

    test_queries = [
        "How do I get a refund for a sale item?",
        "My payment was deducted but order not placed",
        "I forgot my password and can't login",
    ]
    for q in test_queries:
        print(f"\nQuery : {q}")
        for hit in r.retrieve(q, top_k=2):
            print(f"  [{hit['score']:.4f}] {hit['source']}")
            print(f"  {hit['text'][:120]}...")
