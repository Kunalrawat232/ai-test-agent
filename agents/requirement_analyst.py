"""Node 1 — Requirement Analyst Agent."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import get_llm
from prompts.requirement_analyst import REQUIREMENT_ANALYST_PROMPT
from rag import ProjectRetriever
from .state import PipelineState
from .utils import extract_json, trim_context_to_fit


def requirement_analyst_node(state: PipelineState) -> dict[str, Any]:
    """Analyse the raw requirement and produce structured output.

    This node:
    1. Retrieves relevant project context via RAG.
    2. Sends the requirement + context to the LLM.
    3. Returns the structured requirement analysis.
    """
    retriever = ProjectRetriever()

    # Retrieve context relevant to the feature requirement
    context = retriever.query_formatted(
        state.raw_requirement,
        k=10,
    )

    llm = get_llm()

    requirement_text = f"## Feature Requirement\n{state.raw_requirement}"
    context = trim_context_to_fit(
        system_prompt=REQUIREMENT_ANALYST_PROMPT,
        user_content_parts=[requirement_text],
        context=context,
    )

    messages = [
        SystemMessage(content=REQUIREMENT_ANALYST_PROMPT),
        HumanMessage(content=(
            f"{requirement_text}\n\n"
            f"## Project Context (from knowledge base)\n{context}"
        )),
    ]

    response = llm.invoke(messages)

    try:
        analysis = extract_json(response.content)
    except (json.JSONDecodeError, Exception) as exc:
        return {
            "requirement_analysis": {"raw_response": response.content},
            "retrieved_context": context,
            "error_log": [f"RequirementAnalyst JSON parse error: {exc}"],
            "pipeline_status": "running",
        }

    return {
        "requirement_analysis": analysis,
        "retrieved_context": context,
        "pipeline_status": "running",
    }
