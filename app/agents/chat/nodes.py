from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents.chat.prompts import SYSTEM_PROMPT
from app.agents.chat.state import ChatState
from app.agents.chat.tools import build_chat_tools
from app.services.llm_service import get_chat_llm
from langchain_core.messages.utils import trim_messages, count_tokens_approximately

from app.services.llm_service import log_cache_usage

from datetime import datetime
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("Asia/Kolkata"))

def build_agent_node(db, user_id: str, chat_id: int, status_message_id: int):
    tools = build_chat_tools(db, user_id, chat_id, status_message_id)
    llm = get_chat_llm().bind_tools(tools)

    
    async def agent_node(state: ChatState) -> ChatState:
        system = SystemMessage(content=SYSTEM_PROMPT.format(user_context=state.get("user_context", "Nothing yet."),current_date_time=now.strftime("%Y-%m-%d %H:%M:%S %z")))
        trimmed = trim_messages(
            state["messages"],
            max_tokens=4000,
            strategy="last",
            token_counter=count_tokens_approximately,
            include_system=False,
            start_on="human",           # never start the trimmed list mid tool-call sequence
            end_on=("human", "tool"),
        )
        response = await llm.ainvoke([system, *trimmed])
        log_cache_usage(response)
        return {"messages": [response]}

    return agent_node, ToolNode(tools), tools_condition
