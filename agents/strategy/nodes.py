import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from agents.strategy.state import StrategyAgentState, InvestigationStep, TradeThesis, PassDecision
from agents.strategy.prompts import SYSTEM_PROMPT, build_investigation_prompt
from agents.strategy.tools import execute_tool
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def reason_node(state: StrategyAgentState) -> StrategyAgentState:
    """
    LLM call: given current investigation state, decide next action.
    Returns updated state with decision or next tool call.
    """
    # Hard stop: if already decided or error from tool_node, don't make another LLM call
    if state.get("decision") in ("trade", "pass"):
        return state

    prompt = build_investigation_prompt(state)

    try:
        response = await _client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        raw = response.choices[0].message.content.strip()

        # Extract JSON from response
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        action = parsed.get("action")

        if action == "tool":
            # Force pass if max iterations reached
            if state.get("iteration", 0) >= state.get("max_iterations", 7):
                logger.warning(f"Max iterations reached for {state['symbol']} — forcing pass")
                state["decision"] = "pass"
                state["pass_decision"] = PassDecision(
                    symbol=state["symbol"],
                    reason="Max investigation iterations reached",
                    confidence=state.get("confidence", 0.0),
                    investigation_steps=state.get("steps", []),
                    decided_at=datetime.now(timezone.utc),
                )
            else:
                state["current_reasoning"] = parsed.get("reasoning", "")
                state["decision"] = "continue"
                state["_pending_tool"] = {
                    "tool_name": parsed["tool_name"],
                    "tool_input": parsed.get("tool_input", {}),
                    "reasoning": parsed.get("reasoning", ""),
                }

        elif action == "trade":
            current_price = state["current_price"]
            target_pct = float(parsed.get("target_pct", 0.02))
            stop_pct = float(parsed.get("stop_pct", 0.01))

            direction = parsed.get("direction", "LONG")
            if direction == "LONG":
                target_price = round(current_price * (1 + target_pct), 2)
                stop_price = round(current_price * (1 - stop_pct), 2)
            else:
                target_price = round(current_price * (1 - target_pct), 2)
                stop_price = round(current_price * (1 + stop_pct), 2)

            evidence_refs = [
                f"{step.tool_name}: {list(step.tool_result.keys())}"
                for step in state["steps"]
            ]

            state["thesis"] = TradeThesis(
                symbol=state["symbol"],
                direction=direction,
                confidence=float(parsed.get("confidence", 0.0)),
                thesis=parsed.get("thesis", ""),
                entry_price=current_price,
                target_price=target_price,
                stop_price=stop_price,
                proposed_size_pct=settings.max_position_size_pct,
                evidence_refs=evidence_refs,
                investigation_steps=state["steps"],
                formed_at=datetime.now(timezone.utc),
            )
            state["confidence"] = float(parsed.get("confidence", 0.0))
            state["decision"] = "trade"

        elif action == "pass":
            state["pass_decision"] = PassDecision(
                symbol=state["symbol"],
                reason=parsed.get("reason", ""),
                confidence=float(parsed.get("confidence", 0.0)),
                investigation_steps=state["steps"],
                decided_at=datetime.now(timezone.utc),
            )
            state["decision"] = "pass"

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response: {e}\nRaw: {raw}")
        state["decision"] = "pass"
        state["error"] = f"JSON parse error: {e}"

    except Exception as e:
        logger.error(f"reason_node error: {e}")
        state["decision"] = "pass"
        state["error"] = str(e)

    return state


async def tool_node(state: StrategyAgentState) -> StrategyAgentState:
    """Execute the tool chosen by reason_node."""
    pending = state.get("_pending_tool", {})
    if not pending:
        state["decision"] = "pass"
        state["error"] = "tool_node called without pending tool"
        return state

    tool_name = pending["tool_name"]
    tool_input = pending["tool_input"]
    reasoning = pending["reasoning"]

    logger.info(f"Agent calling tool: {tool_name}({tool_input})")

    result = await execute_tool(tool_name, tool_input)

    step = InvestigationStep(
        iteration=state["iteration"],
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result=result,
        reasoning=reasoning,
    )

    state["steps"] = state.get("steps", []) + [step]
    state["iteration"] = state.get("iteration", 0) + 1
    state.pop("_pending_tool", None)

    return state


def route_after_reason(state: StrategyAgentState) -> str:
    """LangGraph conditional edge: where to go after reason_node."""
    if state["decision"] in ("trade", "pass"):
        return "conclude"
    return "tool"


async def conclude_node(state: StrategyAgentState) -> StrategyAgentState:
    """Final node — logs the decision."""
    if state["decision"] == "trade" and state.get("thesis"):
        thesis = state["thesis"]
        logger.info(
            f"TRADE DECISION: {thesis.symbol} {thesis.direction} "
            f"@ {thesis.entry_price} | confidence={thesis.confidence:.2f} "
            f"| steps={len(thesis.investigation_steps)}"
        )
    else:
        pd = state.get("pass_decision")
        reason = pd.reason if pd else state.get("error", "unknown")
        logger.info(f"PASS DECISION: {state['symbol']} — {reason}")

    return state
