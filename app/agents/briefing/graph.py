from langgraph.graph import END, StateGraph

from app.agents.briefing.nodes import compose_node, gather_data_node
from app.agents.briefing.state import BriefingState


def build_briefing_graph():
    graph = StateGraph(BriefingState)
    graph.add_node("gather_data", gather_data_node)
    graph.add_node("compose", compose_node)
    graph.set_entry_point("gather_data")
    graph.add_edge("gather_data", "compose")
    graph.add_edge("compose", END)
    return graph.compile()


async def run_briefing(state: BriefingState) -> str:
    graph = build_briefing_graph()
    result = await graph.ainvoke(state)
    return result["briefing_text"]
