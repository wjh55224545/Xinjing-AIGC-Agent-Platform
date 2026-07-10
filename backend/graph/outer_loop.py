from __future__ import annotations
from langgraph.graph import StateGraph, END

from backend.graph.state import OuterLoopState
from backend.graph.nodes.aggregate import aggregate_node
from backend.graph.nodes.analyze import analyze_node
from backend.graph.nodes.alert import alert_node
from backend.graph.nodes.feedback import feedback_node


def build_outer_loop() -> StateGraph:
    builder = StateGraph(OuterLoopState)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("alert", alert_node)
    builder.add_node("feedback", feedback_node)
    builder.add_edge("aggregate", "analyze")
    builder.add_edge("analyze", "alert")
    builder.add_edge("alert", "feedback")
    builder.add_edge("feedback", END)
    builder.set_entry_point("aggregate")
    return builder.compile()
