from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.nodes import (
    intent_node,
    rag_node,
    chat_node,
    slot_fill_node,
    ask_lead_info_node,
    lead_capture_node,
)


# ── Router (after intent node) ────────────────────────────────────────────────
def router(state: AgentState) -> str:

    # GATE 1: Already captured → RAG + chat for post-signup questions
    if state.get("lead_captured"):
        return "rag"

    any_field = any([
        state.get("lead_name"),
        state.get("lead_email"),
        state.get("lead_platform"),
    ])
    all_fields = all([
        state.get("lead_name"),
        state.get("lead_email"),
        state.get("lead_platform"),
    ])

    # GATE 2: All fields already in state from a previous turn → capture now
    if all_fields:
        return "lead_capture"

    # GATE 3: Some fields exist → still collecting
    if any_field:
        return "slot_fill"

    # GATE 4: No fields yet → intent-driven
    intent = state.get("intent", "greeting")

    if intent == "high_intent":
        return "slot_fill"

    if intent == "inquiry":
        return "rag"

    return "chat"


# ── Router (after slot_fill node) ─────────────────────────────────────────────
# FIX: This is the key change. After slot_fill runs and updates state,
# we check again if all fields are now complete. If yes → lead_capture
# immediately on THIS turn, not the next one.
def after_slot_fill_router(state: AgentState) -> str:
    if all([
        state.get("lead_name"),
        state.get("lead_email"),
        state.get("lead_platform"),
    ]):
        return "lead_capture"
    return "ask_lead"


# ── Build Graph ───────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)

builder.add_node("intent",        intent_node)
builder.add_node("rag",           rag_node)
builder.add_node("chat",          chat_node)
builder.add_node("slot_fill",     slot_fill_node)
builder.add_node("ask_lead",      ask_lead_info_node)
builder.add_node("lead_capture",  lead_capture_node)

builder.set_entry_point("intent")

builder.add_conditional_edges("intent", router, {
    "rag":          "rag",
    "slot_fill":    "slot_fill",
    "lead_capture": "lead_capture",
    "chat":         "chat",
})

builder.add_edge("rag",   "chat")
builder.add_edge("chat",  END)

# FIX: Replaced static edge with conditional router
builder.add_conditional_edges("slot_fill", after_slot_fill_router, {
    "lead_capture": "lead_capture",
    "ask_lead":     "ask_lead",
})

builder.add_edge("ask_lead",     END)
builder.add_edge("lead_capture", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)