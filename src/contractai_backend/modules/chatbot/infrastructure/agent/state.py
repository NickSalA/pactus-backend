"""State definitions for the chatbot graph."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class UserContext(TypedDict, total=False):
    user_id: int
    organization_id: int
    role: str
    full_name: str | None
    allowed_document_types: list[str] | None


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_context: UserContext
    context_route: str
    early_response: str | None
    permission_route: str
    permission_response: str | None
