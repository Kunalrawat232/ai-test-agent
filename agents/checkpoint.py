"""Pipeline checkpoint persistence — save/load state after each node."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import paths

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = paths.generated_reports / "checkpoints"


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    return repr(obj)


def _checkpoint_path(run_id: str) -> Path:
    return CHECKPOINT_DIR / f"{run_id}.json"


def save_checkpoint(run_id: str, node_name: str, state: dict[str, Any]) -> Path:
    """Save pipeline state after a node completes.

    Parameters
    ----------
    run_id:
        Unique identifier for this pipeline run.
    node_name:
        Name of the node that just completed.
    state:
        The full pipeline state dict.

    Returns
    -------
    Path to the checkpoint file.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(run_id)

    checkpoint = {
        "run_id": run_id,
        "last_completed_node": node_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "state": state,
    }

    path.write_text(json.dumps(checkpoint, indent=2, default=_default_serializer))
    logger.info("Checkpoint saved after '%s': %s", node_name, path)
    return path


def load_checkpoint(run_id: str) -> dict[str, Any] | None:
    """Load a previously saved checkpoint.

    Returns
    -------
    The checkpoint dict with keys: run_id, last_completed_node, timestamp, state.
    Returns None if no checkpoint exists.
    """
    path = _checkpoint_path(run_id)
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    logger.info(
        "Checkpoint loaded: run_id=%s, last_node=%s, saved_at=%s",
        data["run_id"], data["last_completed_node"], data["timestamp"],
    )
    return data


def get_latest_checkpoint() -> dict[str, Any] | None:
    """Find and load the most recent checkpoint file.

    Returns
    -------
    The checkpoint dict, or None if no checkpoints exist.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CHECKPOINT_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        return None
    return json.loads(files[-1].read_text())


def list_checkpoints() -> list[dict[str, str]]:
    """Return a summary of all available checkpoints."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in sorted(CHECKPOINT_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text())
            summaries.append({
                "run_id": data["run_id"],
                "last_completed_node": data["last_completed_node"],
                "timestamp": data["timestamp"],
                "feature": data["state"].get("requirement_analysis", {}).get("feature_name", "unknown"),
            })
        except Exception:
            continue
    return summaries
