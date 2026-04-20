import logging
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END

from agents.strategy.state import StrategyAgentState
from agents.strategy.nodes import reason_node, tool_node, conclude_node, route_after_reason
from signals.schemas import SignalEvent
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def build_strategy_graph() -> StateGraph:
    graph = StateGraph(StrategyAgentState)

    graph.add_node("reason", reason_node)
    graph.add_node("tool", tool_node)
    graph.add_node("conclude", conclude_node)

    graph.set_entry_point("reason")

    # After reasoning: go to tool, conclude, or loop back
    graph.add_conditional_edges(
        "reason",
        route_after_reason,
        {
            "tool": "tool",
            "conclude": "conclude",
        },
    )

    # After tool execution, always reason again
    graph.add_edge("tool", "reason")

    # conclude is terminal
    graph.add_edge("conclude", END)

    return graph.compile()


class StrategyAgent:
    def __init__(self):
        self._graph = build_strategy_graph()

    async def investigate(self, signal: SignalEvent) -> StrategyAgentState:
        """
        Run the full ReAct investigation loop for a signal.
        Returns the final state with thesis or pass_decision.
        """
        initial_state: StrategyAgentState = {
            # Trigger
            "symbol": signal.symbol,
            "signal_type": signal.signal_type.value,
            "signal_value": signal.value,
            "current_price": signal.price,
            "signal_context": signal.context,

            # Investigation
            "steps": [],
            "current_reasoning": "",

            # Decision
            "confidence": 0.0,
            "decision": "continue",
            "thesis": None,
            "pass_decision": None,

            # Safety
            "iteration": 0,
            "max_iterations": settings.max_agent_iterations,
            "error": None,

            # Internal
            "_pending_tool": None,
        }

        logger.info(
            f"Strategy Agent starting investigation: {signal.symbol} "
            f"{signal.signal_type.value} @ ${signal.price}"
        )

        final_state = await self._graph.ainvoke(
            initial_state,
            config={"recursion_limit": 50},
        )
        return final_state
