import logging
from dataclasses import dataclass
from typing import Optional

import yaml

from agents.strategy.state import TradeThesis

logger = logging.getLogger(__name__)

POLICY_PATH = "agents/risk/policy.yaml"


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str


class RiskAgent:
    """
    Deterministic risk validation. No LLM.
    Loads rules from policy.yaml and enforces them strictly.
    """

    def __init__(self):
        with open(POLICY_PATH) as f:
            self._policy = yaml.safe_load(f)["risk_policy"]
        logger.info("Risk Agent loaded policy from policy.yaml")

    async def check(
        self,
        thesis: TradeThesis,
        portfolio_value: float,
        open_positions: list,
        daily_pnl_pct: float,
    ) -> RiskCheckResult:

        policy = self._policy

        # 1. Blocked symbols
        if thesis.symbol in policy.get("blocked_symbols", []):
            return RiskCheckResult(False, f"{thesis.symbol} is on the blocked list")

        # 2. Daily loss limit
        if daily_pnl_pct <= -policy["max_daily_loss_pct"]:
            return RiskCheckResult(
                False,
                f"Daily loss limit hit ({daily_pnl_pct:.2%}). Trading halted for today."
            )

        # 3. Max open positions
        if len(open_positions) >= policy["max_open_positions"]:
            return RiskCheckResult(
                False,
                f"Max open positions reached ({len(open_positions)})"
            )

        # 4. Already in position for this symbol
        open_symbols = [p["symbol"] for p in open_positions]
        if thesis.symbol in open_symbols:
            return RiskCheckResult(False, f"Already in open position for {thesis.symbol}")

        # 5. Confidence threshold
        if thesis.confidence < policy["min_confidence_threshold"]:
            return RiskCheckResult(
                False,
                f"Confidence {thesis.confidence:.2f} below threshold {policy['min_confidence_threshold']}"
            )

        # 6. Reward-to-risk ratio
        entry = thesis.entry_price
        target = thesis.target_price
        stop = thesis.stop_price

        if thesis.direction == "LONG":
            reward = target - entry
            risk = entry - stop
        else:
            reward = entry - target
            risk = stop - entry

        if risk <= 0:
            return RiskCheckResult(False, "Invalid stop price — risk is zero or negative")

        rr_ratio = reward / risk
        min_rr = policy["min_target_to_stop_ratio"]
        if rr_ratio < min_rr:
            return RiskCheckResult(
                False,
                f"Reward:risk ratio {rr_ratio:.2f} below minimum {min_rr}"
            )

        # 7. Position size check
        if thesis.proposed_size_pct > policy["max_position_size_pct"]:
            return RiskCheckResult(
                False,
                f"Proposed size {thesis.proposed_size_pct:.2%} exceeds max {policy['max_position_size_pct']:.2%}"
            )

        # 8. Sector concentration
        sector_map = policy.get("sector_map", {})
        if sector_map:
            max_sector_conc = policy.get("max_sector_concentration", 1.0)
            new_sector = sector_map.get(thesis.symbol, "Unknown")
            if new_sector != "Unknown":
                sector_allocation = sum(
                    float(p.get("size_pct", 0))
                    for p in open_positions
                    if sector_map.get(p["symbol"], "Unknown") == new_sector
                ) + thesis.proposed_size_pct
                if sector_allocation > max_sector_conc:
                    return RiskCheckResult(
                        False,
                        f"Sector '{new_sector}' allocation {sector_allocation:.0%} would exceed max {max_sector_conc:.0%}",
                    )

        return RiskCheckResult(True, "All risk checks passed")
