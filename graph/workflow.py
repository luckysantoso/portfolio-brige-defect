"""
graph/workflow.py
Builds and compiles the LangGraph StateGraph for bridge inspection.

Flow
────
image_analyzer
    → rule_validator
        ─── route = "human_review" ──→ human_review   → END
        ─── route = "alert"        ──→ email_alert    → report_generator → END
        ─── route = "normal"       ──→ report_generator → END
"""
from langgraph.graph import END, StateGraph

from graph.nodes import (
    email_alert_stub,
    human_review_placeholder,
    image_analyzer,
    report_generator,
    route_decision,
    rule_validator,
)
from graph.state import InspectionState


def build_graph():
    """Compile and return the bridge inspection LangGraph."""
    g = StateGraph(InspectionState)

    # ── Register nodes ─────────────────────────────────────────────────────
    g.add_node("image_analyzer",  image_analyzer)
    g.add_node("rule_validator",  rule_validator)
    g.add_node("email_alert",     email_alert_stub)
    g.add_node("report_generator", report_generator)
    g.add_node("human_review",    human_review_placeholder)

    # ── Entry point ────────────────────────────────────────────────────────
    g.set_entry_point("image_analyzer")

    # ── Edges ──────────────────────────────────────────────────────────────
    g.add_edge("image_analyzer", "rule_validator")

    g.add_conditional_edges(
        "rule_validator",
        route_decision,
        {
            "human_review":    "human_review",
            "email_alert":     "email_alert",
            "report_generator": "report_generator",
        },
    )

    # After alert → always generate report
    g.add_edge("email_alert", "report_generator")

    # Terminal edges
    g.add_edge("report_generator", END)
    g.add_edge("human_review",     END)

    return g.compile()
