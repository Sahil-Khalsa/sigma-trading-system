from typing import List, Optional, Any, Dict
from typing_extensions import TypedDict
from pydantic import BaseModel
from datetime import datetime


class InvestigationStep(BaseModel):
    iteration: int
    tool_name: str
    tool_input: Dict[str, Any]
    tool_result: Dict[str, Any]
    reasoning: str          # agent's thought before calling this tool


class TradeThesis(BaseModel):
    symbol: str
    direction: str          # LONG | SHORT
    confidence: float
    thesis: str
    entry_price: float
    target_price: float
    stop_price: float
    proposed_size_pct: float
    evidence_refs: List[str]        # tool names + key findings
    investigation_steps: List[InvestigationStep]
    formed_at: datetime


class PassDecision(BaseModel):
    symbol: str
    reason: str
    confidence: float
    investigation_steps: List[InvestigationStep]
    decided_at: datetime


class StrategyAgentState(TypedDict):
    # Trigger
    symbol: str
    signal_type: str
    signal_value: float
    current_price: float
    signal_context: Dict[str, Any]

    # Investigation
    steps: List[InvestigationStep]
    current_reasoning: str

    # Decision
    confidence: float
    decision: str           # "continue" | "trade" | "pass"
    thesis: Optional[TradeThesis]
    pass_decision: Optional[PassDecision]

    # Safety
    iteration: int
    max_iterations: int
    error: Optional[str]

    # Internal — tool call pending (cleared after tool_node runs)
    _pending_tool: Optional[Dict[str, Any]]
