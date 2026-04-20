"""Embedding model factory for RAG pipeline."""

from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings


def get_embedding_model() -> HuggingFaceEmbeddings:
    """Return a free, local embedding model."""
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
