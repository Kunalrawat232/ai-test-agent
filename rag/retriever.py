"""Unified retrieval interface used by all agents."""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import rag_config
from .vectorstore import build_vectorstore


class ProjectRetriever:
    """Wraps the vector store and exposes filtered retrieval."""

    def __init__(self, store: Chroma | None = None) -> None:
        self._store = store or build_vectorstore()

    def query(
        self,
        question: str,
        *,
        k: int | None = None,
        source_type: str | None = None,
    ) -> list[Document]:
        """Retrieve the most relevant chunks.

        Parameters
        ----------
        question:
            Natural-language query.
        k:
            Number of results (defaults to ``rag_config.retrieval_k``).
        source_type:
            Optional filter — one of ``codebase``, ``api_schema``,
            ``documentation``, ``existing_test``.
        """
        k = k or rag_config.retrieval_k
        search_kwargs: dict = {"k": k}
        if source_type:
            search_kwargs["filter"] = {"source_type": source_type}

        retriever = self._store.as_retriever(search_kwargs=search_kwargs)
        return retriever.invoke(question)

    def query_formatted(
        self,
        question: str,
        *,
        k: int | None = None,
        source_type: str | None = None,
    ) -> str:
        """Return retrieved context as a single formatted string."""
        docs = self.query(question, k=k, source_type=source_type)
        if not docs:
            return "(No relevant context found in knowledge base.)"

        parts: list[str] = []
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata
            header = f"[{i}] {meta.get('filename', 'unknown')} ({meta.get('source_type', '?')})"
            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)
