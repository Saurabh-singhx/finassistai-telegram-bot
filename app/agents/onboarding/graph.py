from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.onboarding.nodes import run_onboarding_turn
from app.agents.onboarding.state import OnboardingState
from app.models.user import User

# The DB session/user are threaded through via closures rather than the graph state itself,
# since SQLAlchemy sessions aren't serializable state values. Keeping the graph structure here
# (rather than calling run_onboarding_turn directly from the handler) is what keeps this agent
# structurally consistent with chat/ and briefing/, even though the flow is a single node.


def build_onboarding_graph(db: AsyncSession, user: User):
    async def handle_turn(state: OnboardingState) -> OnboardingState:
        reply = await run_onboarding_turn(db, user, state.get("incoming_text", ""))
        state["reply"] = reply
        state["finished"] = user.onboarding_state.get("completed", False)
        return state

    graph = StateGraph(OnboardingState)
    graph.add_node("handle_turn", handle_turn)
    graph.set_entry_point("handle_turn")
    graph.add_edge("handle_turn", END)
    return graph.compile()


async def run_onboarding(db: AsyncSession, user: User, incoming_text: str) -> tuple[str, bool]:
    graph = build_onboarding_graph(db, user)
    result = await graph.ainvoke({"user_id": str(user.id), "telegram_id": user.telegram_id, "incoming_text": incoming_text})
    return result["reply"], result["finished"]
