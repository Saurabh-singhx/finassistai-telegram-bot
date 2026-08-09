from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    user_context: str  # rendered summary of profile + long-term memory, injected into system prompt
