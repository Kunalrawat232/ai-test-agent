"""LangGraph workflow — the multi-agent pipeline orchestrator.

Graph topology:

    ┌──────────────────┐
    │  Requirement      │
    │  Analyst (Node 1) │
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │  Test Designer    │
    │  (Node 2)         │
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │  Code Generator   │
    │  (Node 3)         │
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │  Execution        │◄──────────┐
    │  (Node 4)         │           │
    └────────┬─────────┘           │
             │                      │
        ┌────▼────┐                 │
        │ should   │   "debug"      │
        │ retry?   │────────►┌──────┴──────┐
        └────┬────┘         │  Debug Loop  │
             │ "done"       │  (Node 5)    │
             │              └──────────────┘
    ┌────────▼─────────┐
    │  Finalise         │
    │  (Terminal)        │
    └──────────────────┘
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from config.settings import paths, exec_config
from .state import PipelineState
from .requirement_analyst import requirement_analyst_node
from .test_designer import test_designer_node
from .code_generator import code_generator_node
from .execution_debug import execution_node, debug_node, should_retry
from .checkpoint import save_checkpoint, load_checkpoint

logger = logging.getLogger(__name__)

# Ordered list of nodes in the linear part of the pipeline (before the retry loop).
# Used to determine which node to resume from.
NODE_ORDER = [
    "requirement_analyst",
    "test_designer",
    "code_generator",
    "execution",
    "debug",
    "finalise",
]


# ---------------------------------------------------------------------------
# Checkpoint-saving wrapper
# ---------------------------------------------------------------------------

def _make_checkpointing_node(node_name: str, node_fn, run_id: str):
    """Wrap a node function so it saves a checkpoint after completing."""

    def wrapped(state: PipelineState) -> dict[str, Any]:
        result = node_fn(state)

        # Build the merged state for checkpointing
        state_dict = state.dict() if hasattr(state, "dict") else dict(state)
        if isinstance(result, dict):
            state_dict.update(result)

        save_checkpoint(run_id, node_name, state_dict)
        return result

    wrapped.__name__ = node_fn.__name__
    wrapped.__doc__ = node_fn.__doc__
    return wrapped


# ---------------------------------------------------------------------------
# Terminal node — write final report
# ---------------------------------------------------------------------------

def finalise_node(state: PipelineState) -> dict[str, Any]:
    """Produce a human-readable summary report and persist it."""
    exec_result = state.execution_result
    debug = state.debug_analysis
    all_passed = exec_result.get("all_passed", False)

    status = "PASSED" if all_passed else "FAILED"
    if not all_passed and state.retry_count >= state.max_retries:
        status = "FAILED (retries exhausted)"

    report_lines = [
        f"# Test Pipeline Report",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Feature:** {state.requirement_analysis.get('feature_name', 'unknown')}",
        f"**Status:** {status}",
        f"**Retries used:** {state.retry_count} / {state.max_retries}",
        "",
        "## Execution Summary",
        f"- Total test files: {exec_result.get('total_files', 0)}",
        f"- Failed files: {exec_result.get('failed_files', [])}",
        "",
    ]

    # Bug reports from debug agent
    bug_reports = debug.get("bug_reports", [])
    if bug_reports:
        report_lines.append("## Real Bugs Found")
        for br in bug_reports:
            report_lines.append(f"### {br.get('title', 'Untitled')}")
            report_lines.append(f"**Severity:** {br.get('severity', 'unknown')}")
            report_lines.append(f"**Expected:** {br.get('expected', '')}")
            report_lines.append(f"**Actual:** {br.get('actual', '')}")
            report_lines.append("")

    # Error log
    if state.error_log:
        report_lines.append("## Pipeline Errors")
        for err in state.error_log:
            report_lines.append(f"- {err}")

    report_text = "\n".join(report_lines)

    # Persist report
    reports_dir = paths.generated_reports
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"report_{ts}.md"
    report_path.write_text(report_text)

    final_status = "passed" if all_passed else "failed"

    return {
        "pipeline_status": final_status,
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(run_id: str | None = None, entry_point: str = "requirement_analyst") -> StateGraph:
    """Construct and compile the LangGraph workflow.

    Parameters
    ----------
    run_id:
        Unique run identifier for checkpoint persistence.
    entry_point:
        Which node to start from (for resume support).
    """
    rid = run_id or uuid.uuid4().hex[:12]

    # Wrap each node with checkpointing
    nodes = {
        "requirement_analyst": _make_checkpointing_node("requirement_analyst", requirement_analyst_node, rid),
        "test_designer": _make_checkpointing_node("test_designer", test_designer_node, rid),
        "code_generator": _make_checkpointing_node("code_generator", code_generator_node, rid),
        "execution": _make_checkpointing_node("execution", execution_node, rid),
        "debug": _make_checkpointing_node("debug", debug_node, rid),
        "finalise": _make_checkpointing_node("finalise", finalise_node, rid),
    }

    graph = StateGraph(PipelineState)

    # -- Register nodes --
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # -- Edges: linear pipeline --
    graph.set_entry_point(entry_point)

    # Only add edges for nodes at or after the entry point
    entry_idx = NODE_ORDER.index(entry_point)
    linear_edges = [
        ("requirement_analyst", "test_designer"),
        ("test_designer", "code_generator"),
        ("code_generator", "execution"),
    ]
    for src, dst in linear_edges:
        if NODE_ORDER.index(src) >= entry_idx:
            graph.add_edge(src, dst)

    # -- Conditional edge after execution --
    graph.add_conditional_edges(
        "execution",
        should_retry,
        {
            "debug": "debug",
            "done": "finalise",
        },
    )

    # -- After debug, re-run execution --
    graph.add_edge("debug", "execution")

    # -- Terminal --
    graph.add_edge("finalise", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def run_pipeline(
    requirement: str,
    *,
    max_retries: int | None = None,
    resume_run_id: str | None = None,
) -> dict[str, Any]:
    """Run the full testing pipeline for a given feature requirement.

    Parameters
    ----------
    requirement:
        Free-text feature requirement or user story.
    max_retries:
        Override the default retry limit from config.
    resume_run_id:
        If provided, resume from the last checkpoint of this run.

    Returns
    -------
    Final pipeline state dict.
    """
    entry_point = "requirement_analyst"
    initial_kwargs: dict[str, Any] = {
        "raw_requirement": requirement,
        "max_retries": max_retries or exec_config.max_retries,
        "pipeline_status": "running",
    }
    run_id = resume_run_id

    # Resume from checkpoint if requested
    if resume_run_id:
        checkpoint = load_checkpoint(resume_run_id)
        if checkpoint:
            last_node = checkpoint["last_completed_node"]
            last_idx = NODE_ORDER.index(last_node)

            # Start from the next node after the last completed one
            if last_idx + 1 < len(NODE_ORDER):
                entry_point = NODE_ORDER[last_idx + 1]
            else:
                logger.info("Pipeline already completed in checkpoint. Re-running finalise.")
                entry_point = "finalise"

            # Restore state from checkpoint
            initial_kwargs = checkpoint["state"]
            initial_kwargs["pipeline_status"] = "running"

            logger.info(
                "Resuming run '%s' from node '%s' (last completed: '%s')",
                resume_run_id, entry_point, last_node,
            )
        else:
            logger.warning("No checkpoint found for run_id '%s'. Starting fresh.", resume_run_id)
            run_id = None

    graph = build_graph(run_id=run_id, entry_point=entry_point)
    initial_state = PipelineState(**initial_kwargs)
    final_state = graph.invoke(initial_state)

    return final_state
