"""Граф агента. Маршрут выбирает Python-код по полю state["route"], LLM на него не влияет.

    guard_input → schema_linking → detect_ambiguity → generate_sql → validate_sql → execute
                       ↑                 │                 ↑              │            │
                       └──── clarify ←───┘                 └ self_correct ←┴────────────┘
    execute → explain_and_visualize → END;  любой отказ → refuse → END

Полная диаграмма — docs/graph.md.
"""

from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import AgentNodes
from app.agent.state import AgentContext, AgentState


def node(fn: Any) -> Any:
    """Узлы принимают (state, runtime, config): LangGraph это поддерживает,
    но его типовые протоколы такую сигнатуру не описывают."""
    return cast(Any, fn)


def route(state: AgentState) -> str:
    return state.get("route") or "refuse"


def build_graph(
    nodes: AgentNodes, checkpointer: BaseCheckpointSaver[str] | None
) -> CompiledStateGraph[AgentState, AgentContext]:
    g = StateGraph(AgentState, context_schema=AgentContext)
    g.add_node("guard_input", node(nodes.guard_input))
    g.add_node("schema_linking", node(nodes.schema_linking))
    g.add_node("detect_ambiguity", node(nodes.detect_ambiguity))
    g.add_node("clarify", node(nodes.clarify))
    g.add_node("generate_sql", node(nodes.generate_sql))
    g.add_node("validate_sql", node(nodes.validate_sql))
    g.add_node("self_correct", node(nodes.self_correct))
    g.add_node("execute", node(nodes.execute))
    g.add_node("explain_and_visualize", node(nodes.explain_and_visualize))
    g.add_node("refuse", node(nodes.refuse))

    g.add_edge(START, "guard_input")
    g.add_conditional_edges("guard_input", route, {"ok": "schema_linking", "refuse": "refuse"})
    g.add_edge("schema_linking", "detect_ambiguity")
    g.add_conditional_edges(
        "detect_ambiguity",
        route,
        {"clarify": "clarify", "generate": "generate_sql", "refuse": "refuse"},
    )
    g.add_edge("clarify", "schema_linking")
    g.add_conditional_edges("generate_sql", route, {"validate": "validate_sql", "refuse": "refuse"})
    g.add_conditional_edges(
        "validate_sql",
        route,
        {"execute": "execute", "retry": "self_correct", "refuse": "refuse"},
    )
    g.add_edge("self_correct", "generate_sql")
    g.add_conditional_edges(
        "execute",
        route,
        {"explain": "explain_and_visualize", "retry": "self_correct", "refuse": "refuse"},
    )
    g.add_edge("explain_and_visualize", END)
    g.add_edge("refuse", END)
    return g.compile(checkpointer=checkpointer)
