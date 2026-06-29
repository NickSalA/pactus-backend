"""Structured outputs used by the multi-agent chatbot graph."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ContextAgentDecision(BaseModel):
    route: Literal["a2_permissions", "n1_early_response"]
    response: str | None = None


class PermissionAgentDecision(BaseModel):
    route: Literal["a3_conversation", "n2_denied_response"]
    response: str | None = None


def coerce_content_to_text(content: Any) -> str:
    """Normalize LangChain content payloads into plain text."""
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def parse_structured_decision[T: BaseModel](raw_content: Any, schema: type[T]) -> T:
    """Parse a JSON decision emitted by a routing agent."""
    text = coerce_content_to_text(raw_content).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The routing agent did not return a JSON object")

    payload = json.loads(text[start : end + 1])
    return schema.model_validate(payload)
