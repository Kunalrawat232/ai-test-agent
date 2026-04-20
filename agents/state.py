"""LangGraph shared state schema for the multi-agent pipeline."""

from __future__ import annotations

from typing import Any, Annotated
from pydantic import BaseModel, Field
import operator


def _merge_dicts(a: dict, b: dict) -> dict:
    """Shallow merge — newer values win."""
    return {**a, **b}


class PipelineState(BaseModel):
    """Typed state passed through every node in the LangGraph workflow.

    Each field uses a reducer so that nodes can emit partial updates
    without clobbering previous values.
    """

    # -- Inputs --
    raw_requirement: str = ""

    # -- RAG context retrieved for the current requirement --
    retrieved_context: str = ""

    # -- Node 1 output: Requirement Analyst --
    requirement_analysis: Annotated[dict[str, Any], _merge_dicts] = Field(default_factory=dict)

    # -- Node 2 output: Test Designer --
    test_plan: Annotated[dict[str, Any], _merge_dicts] = Field(default_factory=dict)

    # -- Node 3 output: Code Generator --
    generated_code: Annotated[dict[str, Any], _merge_dicts] = Field(default_factory=dict)

    # -- Node 4 output: Execution results --
    execution_result: Annotated[dict[str, Any], _merge_dicts] = Field(default_factory=dict)

    # -- Node 5 output: Debug analysis --
    debug_analysis: Annotated[dict[str, Any], _merge_dicts] = Field(default_factory=dict)

    # -- Control flow --
    retry_count: int = 0
    max_retries: int = 3
    pipeline_status: str = "pending"  # pending | running | passed | failed | error
    error_log: Annotated[list[str], operator.add] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
