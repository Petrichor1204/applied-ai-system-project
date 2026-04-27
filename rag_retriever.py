"""
rag_retriever.py
----------------
Lightweight Retrieval-Augmented Generation (RAG) engine for PawPal+.

Uses TF-IDF (term frequency-inverse document frequency) to score the
relevance of each knowledge-base document against a query, then returns
the top-K documents so the LLM can ground its answer in verified facts.

No external ML dependencies required beyond numpy (which ships with the
project environment).
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    "a", "an", "the", "is", "in", "it", "of", "and", "or", "to", "for",
    "with", "on", "at", "by", "this", "that", "be", "are", "was", "were",
    "as", "its", "has", "have", "had", "not", "but", "from", "do", "so",
    "if", "all", "my", "me", "we", "our", "your", "their", "can", "will",
    "may", "more", "how", "what", "when", "which",
}


def _tokenize(text: str) -> List[str]:
    """Lowercase, strip punctuation, remove stop words."""
    tokens = re.findall(r"[a-z]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


class RAGRetriever:
    """
    TF-IDF retriever over a JSON knowledge base.

    Parameters
    ----------
    kb_path : str or Path
        Path to a JSON file containing a list of document objects.
        Each document must have at least ``"content"`` and ``"title"`` keys.
        Optional keys: ``"tags"``, ``"species"``, ``"id"``.
    top_k : int
        Number of documents to return per query (default 3).
    """

    def __init__(self, kb_path: str | Path, top_k: int = 3):
        self.kb_path = Path(kb_path)
        self.top_k = top_k
        self.documents: List[Dict] = []
        self._vocab: Dict[str, int] = {}
        self._idf: np.ndarray = np.array([])
        self._doc_vectors: np.ndarray = np.array([])

        self._load_and_index()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_and_index(self) -> None:
        """Load the KB from disk and build the TF-IDF index."""
        if not self.kb_path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {self.kb_path}")

        with open(self.kb_path, encoding="utf-8") as fh:
            self.documents = json.load(fh)

        if not self.documents:
            logger.warning("Knowledge base is empty; RAG retrieval will return nothing.")
            return

        # Build vocabulary from all document text (content + title + tags)
        corpus_tokens: List[List[str]] = []
        for doc in self.documents:
            tag_text = " ".join(doc.get("tags", []))
            combined = f"{doc['title']} {doc['content']} {tag_text}"
            corpus_tokens.append(_tokenize(combined))

        all_terms = sorted({t for tokens in corpus_tokens for t in tokens})
        self._vocab = {term: idx for idx, term in enumerate(all_terms)}
        V = len(self._vocab)
        N = len(self.documents)

        # Compute TF matrix  (N × V)
        tf_matrix = np.zeros((N, V), dtype=np.float32)
        for i, tokens in enumerate(corpus_tokens):
            if not tokens:
                continue
            for token in tokens:
                if token in self._vocab:
                    tf_matrix[i, self._vocab[token]] += 1
            tf_matrix[i] /= len(tokens)

        # Compute IDF  (V,)
        doc_freq = (tf_matrix > 0).sum(axis=0).astype(np.float32)
        self._idf = np.log((N + 1) / (doc_freq + 1)) + 1.0  # smoothed

        # Pre-compute TF-IDF document vectors and L2-normalize
        self._doc_vectors = tf_matrix * self._idf  # broadcast
        norms = np.linalg.norm(self._doc_vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        self._doc_vectors /= norms

        logger.info(
            "RAG index built: %d documents, vocabulary size %d", N, V
        )

    def _query_vector(self, query: str) -> np.ndarray:
        """Convert a query string to a normalized TF-IDF vector."""
        tokens = _tokenize(query)
        V = len(self._vocab)
        vec = np.zeros(V, dtype=np.float32)
        if not tokens:
            return vec
        for token in tokens:
            if token in self._vocab:
                vec[self._vocab[token]] += 1
        vec /= max(len(tokens), 1)
        vec *= self._idf
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        species_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Retrieve the top-K most relevant documents for *query*.

        Parameters
        ----------
        query : str
            Natural-language question or description.
        species_filter : str, optional
            If provided (e.g. ``"dog"``), documents tagged for a different
            species are penalised (score multiplied by 0.4) but not removed,
            so cross-species tips can still surface when relevant.

        Returns
        -------
        list of dict
            Each dict contains the original document keys plus a
            ``"score"`` float in [0, 1].
        """
        if self._doc_vectors.size == 0:
            return []

        q_vec = self._query_vector(query)
        scores = self._doc_vectors @ q_vec  # cosine similarity

        # Apply species relevance boost
        if species_filter:
            for i, doc in enumerate(self.documents):
                doc_species = doc.get("species", "all")
                if doc_species not in ("all", species_filter):
                    scores[i] *= 0.4

        top_indices = np.argsort(scores)[::-1][: self.top_k]
        results = []
        for idx in top_indices:
            if scores[idx] < 0.01:  # skip near-zero relevance docs
                continue
            result = dict(self.documents[idx])
            result["score"] = float(scores[idx])
            results.append(result)

        logger.debug(
            "RAG query=%r species_filter=%r → %d results (top score=%.3f)",
            query[:60],
            species_filter,
            len(results),
            results[0]["score"] if results else 0.0,
        )
        return results

    def format_context(self, docs: List[Dict]) -> str:
        """
        Render retrieved documents as a numbered context block for the LLM prompt.
        """
        if not docs:
            return "(No relevant knowledge-base articles found.)"
        lines = ["[Retrieved pet-care knowledge]"]
        for i, doc in enumerate(docs, 1):
            lines.append(f"{i}. {doc['title']} (relevance {doc['score']:.2f})")
            lines.append(f"   {doc['content']}")
        return "\n".join(lines)