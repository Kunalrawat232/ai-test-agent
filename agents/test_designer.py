"""Node 2 — Test Designer Agent."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import get_llm
from prompts.test_designer import TEST_DESIGNER_PROMPT
from .state import PipelineState
from .utils import extract_json, trim_context_to_fit


def test_designer_node(state: PipelineState) -> dict[str, Any]:
    """Design comprehensive test cases from the requirement analysis.

    Inputs from state:
    - requirement_analysis (from Node 1)
    - retrieved_context (RAG context)

    Outputs:
    - test_plan: structured test suites, cases, data, coverage matrix
    """
    llm = get_llm()

    analysis_json = json.dumps(state.requirement_analysis, indent=2)
    analysis_text = f"## Requirement Analysis\n```json\n{analysis_json}\n```"

    context = trim_context_to_fit(
        system_prompt=TEST_DESIGNER_PROMPT,
        user_content_parts=[analysis_text],
        context=state.retrieved_context,
    )

    messages = [
        SystemMessage(content=TEST_DESIGNER_PROMPT),
        HumanMessage(content=(
            f"{analysis_text}\n\n"
            f"## Project Context\n{context}"
        )),
    ]

    response = llm.invoke(messages)

    try:
        test_plan = extract_json(response.content)
    except (json.JSONDecodeError, Exception) as exc:
        return {
            "test_plan": {"raw_response": response.content},
            "error_log": [f"TestDesigner JSON parse error: {exc}"],
        }

    return {"test_plan": test_plan}
