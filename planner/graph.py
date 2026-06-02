from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from planner.nodes import (
    apply_replan_constraints_node,
    approval_node,
    clarification_node,
    classify_blocks_node,
    compute_free_blocks_node,
    finalize_node,
    generate_explanation_node,
    interpret_rejection_node,
    normalize_time_node,
    parse_input_node,
    place_tasks_node,
    rank_tasks_node,
    validate_input_node,
    validate_plan_node,
)
from planner.state import PlannerState


def route_after_validation(state: PlannerState) -> str:
    if state.get("clarification_questions"):
        return "missing_info"
    if any(issue.blocking for issue in state.get("input_errors", [])):
        return "invalid_input"
    return "valid"


def route_after_approval(state: PlannerState) -> str:
    if state.get("approval_status") == "approved":
        return "approved"
    if state.get("approval_status") == "rejected":
        if state.get("replan_count", 0) >= 3:
            return "limit"
        return "rejected"
    return "pending"


def build_planner_graph(checkpointer=None):
    graph = StateGraph(PlannerState)
    graph.add_node("parse_input_node", parse_input_node)
    graph.add_node("apply_replan_constraints_node", apply_replan_constraints_node)
    graph.add_node("validate_input_node", validate_input_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("normalize_time_node", normalize_time_node)
    graph.add_node("compute_free_blocks_node", compute_free_blocks_node)
    graph.add_node("classify_blocks_node", classify_blocks_node)
    graph.add_node("rank_tasks_node", rank_tasks_node)
    graph.add_node("place_tasks_node", place_tasks_node)
    graph.add_node("validate_plan_node", validate_plan_node)
    graph.add_node("generate_explanation_node", generate_explanation_node)
    graph.add_node("approval_node", approval_node)
    graph.add_node("interpret_rejection_node", interpret_rejection_node)
    graph.add_node("finalize_node", finalize_node)

    graph.add_edge(START, "parse_input_node")
    graph.add_edge("parse_input_node", "apply_replan_constraints_node")
    graph.add_edge("apply_replan_constraints_node", "validate_input_node")
    graph.add_conditional_edges(
        "validate_input_node",
        route_after_validation,
        {
            "missing_info": "clarification_node",
            "invalid_input": END,
            "valid": "normalize_time_node",
        },
    )
    graph.add_edge("clarification_node", END)
    graph.add_edge("normalize_time_node", "compute_free_blocks_node")
    graph.add_edge("compute_free_blocks_node", "classify_blocks_node")
    graph.add_edge("classify_blocks_node", "rank_tasks_node")
    graph.add_edge("rank_tasks_node", "place_tasks_node")
    graph.add_edge("place_tasks_node", "validate_plan_node")
    graph.add_edge("validate_plan_node", "generate_explanation_node")
    graph.add_edge("generate_explanation_node", "approval_node")
    graph.add_conditional_edges(
        "approval_node",
        route_after_approval,
        {
            "approved": "finalize_node",
            "rejected": "interpret_rejection_node",
            "pending": END,
            "limit": END,
        },
    )
    graph.add_edge("interpret_rejection_node", END)
    graph.add_edge("finalize_node", END)

    return graph.compile(checkpointer=checkpointer)
