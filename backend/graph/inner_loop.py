from __future__ import annotations
from langgraph.graph import StateGraph, END

from backend.graph.state import InnerLoopState
from backend.graph.nodes.collect import collect_node
from backend.graph.nodes.recognize import recognize_node
from backend.graph.nodes.store import store_node


def build_inner_loop() -> StateGraph:
    builder = StateGraph(InnerLoopState)
    builder.add_node("collect", collect_node)
    builder.add_node("recognize", recognize_node)
    builder.add_node("store", store_node)
    builder.add_edge("collect", "recognize")
    builder.add_edge("recognize", "store")
    builder.add_edge("store", END)
    builder.set_entry_point("collect")
    return builder.compile()
