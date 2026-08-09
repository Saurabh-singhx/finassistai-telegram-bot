from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.agents.chat.nodes import build_agent_node
from app.agents.chat.state import ChatState
from app.config import settings
from app.database import AsyncSessionLocal


def build_chat_graph(db, user_id: str, tool_node, tools_condition, agent_node):
    graph = StateGraph(ChatState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph


async def run_chat_turn(user_id: str, thread_id: str, user_context: str, user_text: str, chat_id: int, status_message_id: int) -> str:
    """Compiles the graph with a Postgres-backed checkpointer for short-term (per-thread) memory,
    runs one turn, and returns the assistant's reply text. Opens its own DB session (rather than
    reusing the caller's) so it can stay alive for the full duration of any tool calls made mid-turn."""
    async with AsyncSessionLocal() as db:
        agent_node, tool_node, tools_condition = build_agent_node(db, user_id, chat_id, status_message_id)
        graph = build_chat_graph(db, user_id, tool_node, tools_condition, agent_node)

        # AsyncPostgresSaver reuses the same Postgres DB as everything else (checkpoints tables are
        # auto-created on .setup()). This is what gives the bot short-term memory across a session.
        async with AsyncPostgresSaver.from_conn_string(_psycopg_dsn(settings.DATABASE_URL)) as checkpointer:
            await checkpointer.setup()
            compiled = graph.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            result = await compiled.ainvoke(
                {"messages": [("user", user_text)], "user_id": user_id, "user_context": user_context}, config=config
            )
            last = result["messages"][-1]

            if isinstance(last.content, str):
                return last.content

            if isinstance(last.content, list):
                return "".join(
                    block["text"]
                    for block in last.content
                    if isinstance(block, dict)
                    and block.get("type") == "text"
                    and "text" in block
                )

            return str(last.content)


def _psycopg_dsn(async_dsn: str) -> str:
    """AsyncPostgresSaver needs a plain psycopg DSN, not the sqlalchemy+asyncpg one used elsewhere."""
    return async_dsn.replace("postgresql+asyncpg://", "postgresql://")
