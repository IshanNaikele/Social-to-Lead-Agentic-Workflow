from typing import TypedDict, Optional, List
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: List[BaseMessage]          # full conversation history
    intent: Optional[str]                # "greeting" | "inquiry" | "high_intent"
    lead_name: Optional[str]
    lead_email: Optional[str]
    lead_platform: Optional[str]
    lead_captured: bool                  # guard flag - prevents premature tool call
    rag_context: Optional[str]           # what was retrieved