from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents.chat.prompts import SYSTEM_PROMPT
from app.agents.chat.state import ChatState
from app.agents.chat.tools import build_chat_tools
from app.services.llm_service import get_chat_llm
from app.services.telegram_service import delete_status

def build_agent_node(db, user_id: str, chat_id: int, status_message_id: int):
    tools = build_chat_tools(db, user_id, chat_id, status_message_id)
    llm = get_chat_llm().bind_tools(tools)

    
    async def agent_node(state: ChatState) -> ChatState:
        system = SystemMessage(content=SYSTEM_PROMPT.format(user_context=state.get("user_context", "Nothing yet.")))
        response = await llm.ainvoke([system, *state["messages"]])
        return {"messages": [response]}

    return agent_node, ToolNode(tools), tools_condition
