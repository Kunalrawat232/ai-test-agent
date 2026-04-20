"""ChromaDB vector store management for project context."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config.settings import rag_config, paths
from .embeddings import get_embedding_model

# File extensions we know how to ingest
_CODE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".feature", ".gherkin", ".robot",
}


def _collect_files(directory: Path) -> list[Path]:
    """Recursively collect indexable files from a directory."""
    if not directory.exists():
        return []
    return [
        f for f in directory.rglob("*")
        if f.is_file() and f.suffix in _CODE_EXTS and f.stat().st_size < 500_000
    ]


def _file_to_document(path: Path, source_label: str) -> Document:
    """Convert a file to a LangChain Document with metadata."""
    text = path.read_text(errors="replace")
    return Document(
        page_content=text,
        metadata={
            "source": str(path),
            "source_type": source_label,
            "filename": path.name,
            "extension": path.suffix,
            "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
        },
    )


def _load_all_context_documents() -> list[Document]:
    """Load documents from every context source directory."""
    sources = [
        (paths.context_codebase, "codebase"),
        (paths.context_api, "api_schema"),
        (paths.context_docs, "documentation"),
        (paths.context_tests, "existing_test"),
    ]
    docs: list[Document] = []
    for directory, label in sources:
        for fpath in _collect_files(directory):
            docs.append(_file_to_document(fpath, label))
    return docs


def _split_documents(docs: list[Document]) -> list[Document]:
    """Chunk documents for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=rag_config.chunk_size,
        chunk_overlap=rag_config.chunk_overlap,
        separators=["\nclass ", "\ndef ", "\n\n", "\n", " "],
    )
    return splitter.split_documents(docs)


def build_vectorstore(force_rebuild: bool = False) -> Chroma:
    """Build or load the Chroma vector store.

    If the store already exists on disk and ``force_rebuild`` is False,
    it is loaded directly.  Otherwise all context directories are
    scanned, chunked, embedded and persisted.
    """
    persist_dir = Path(rag_config.persist_dir)
    embeddings = get_embedding_model()

    if persist_dir.exists() and not force_rebuild:
        return Chroma(
            collection_name=rag_config.collection_name,
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
        )

    raw_docs = _load_all_context_documents()
    if not raw_docs:
        # Return empty store so downstream code still works
        return Chroma(
            collection_name=rag_config.collection_name,
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
        )

    chunks = _split_documents(raw_docs)

    store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=rag_config.collection_name,
        persist_directory=str(persist_dir),
    )
    return store


def add_documents_to_store(
    store: Chroma, docs: Sequence[Document]
) -> None:
    """Incrementally add new documents to an existing store."""
    chunks = _split_documents(list(docs))
    if chunks:
        store.add_documents(chunks)
