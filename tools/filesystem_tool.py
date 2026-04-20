"""File system read/write tools for agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from config.settings import PROJECT_ROOT

# Sandbox: only allow operations under the project root
_ALLOWED_ROOT = PROJECT_ROOT


def _safe_path(raw: str) -> Path:
    """Resolve a path and ensure it stays within the project sandbox."""
    p = Path(raw).resolve()
    if not str(p).startswith(str(_ALLOWED_ROOT)):
        raise PermissionError(f"Path {p} is outside the project sandbox")
    return p


@tool
def read_file(file_path: str) -> dict[str, Any]:
    """Read the contents of a file within the project directory.

    Args:
        file_path: Absolute or relative path to read.
    """
    try:
        p = _safe_path(file_path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {p}"}
        content = p.read_text(errors="replace")
        # Truncate very large files to avoid context blow-up
        if len(content) > 50_000:
            content = content[:50_000] + "\n\n... [truncated at 50 000 chars]"
        return {"success": True, "path": str(p), "content": content}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool
def write_file(file_path: str, content: str) -> dict[str, Any]:
    """Write content to a file, creating parent directories as needed.

    Args:
        file_path: Destination path (must be within the project directory).
        content: Text content to write.
    """
    try:
        p = _safe_path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"success": True, "path": str(p), "bytes_written": len(content)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool
def list_directory(dir_path: str = ".", pattern: str = "*") -> dict[str, Any]:
    """List files matching a glob pattern under a directory.

    Args:
        dir_path: Directory to list (defaults to project root).
        pattern: Glob pattern (e.g. '*.py', '**/*.ts').
    """
    try:
        p = _safe_path(dir_path)
        if not p.is_dir():
            return {"success": False, "error": f"Not a directory: {p}"}
        files = sorted(str(f.relative_to(p)) for f in p.rglob(pattern) if f.is_file())
        return {"success": True, "directory": str(p), "files": files[:500]}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
