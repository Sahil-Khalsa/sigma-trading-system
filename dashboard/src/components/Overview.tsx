import { useEffect, useState } from "react";
import { TrendingUp, Zap, Brain, DollarSign, Activity } from "lucide-react";
import type { WSEvent } from "../hooks/useWebSocket";
import SignalFeed from "./SignalFeed";
import AgentTrace from "./AgentTrace";

type Props = { events: WSEvent[] };

type Account = { portfolio_value: number; cash: number; daily_pl: number; daily_pl_pct: number };

export default function Overview({ events }: Props) {
  const [account, setAccount] = useState<Account | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/portfolio/state")
      .then(r => r.json())
      .then(d => setAccount(d.account))
      .catch(() => {});
  }, []);

  const signalsToday = events.filter(e => e.type === "signal_fired").length;
  const tradesDecided = events.filter(e => e.type === "trade_decision").length;
  const passed = events.filter(e => e.type === "trade_passed").length;

  const pnl = account?.daily_pl ?? 0;
  const pnlPct = account?.daily_pl_pct ?? 0;

  return (
    <>
      {/* Stat cards */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label"><DollarSign /> Portfolio Value</div>
          <div className="stat-value font-mono">
            {account ? `$${account.portfolio_value.toLocaleString()}` : "—"}
          </div>
          <div className="stat-sub">
            Cash: {account ? `$${account.cash.toLocaleString()}` : "—"}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><TrendingUp /> Daily P&amp;L</div>
          <div className={`stat-value ${pnl >= 0 ? "pos" : "neg"}`}>
            {account ? `${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)}` : "—"}
          </div>
          <div className="stat-sub" style={{ color: pnl >= 0 ? "var(--green)" : "var(--red)" }}>
            {account ? `${pnl >= 0 ? "+" : ""}${(pnlPct * 100).toFixed(3)}%` : "—"}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><Zap /> Signals Today</div>
          <div className="stat-value">{signalsToday}</div>
          <div className="stat-sub">{passed} passed · {tradesDecided} traded</div>
        </div>

        <div className="stat-card">
          <div className="stat-label"><Brain /> Agent Status</div>
          <div className="stat-value" style={{ fontSize: 18, paddingTop: 4 }}>
            <span className="badge green">Active</span>
          </div>
          <div className="stat-sub">LangGraph ReAct · GPT-4o</div>
        </div>
      </div>

      {/* Live feed + latest investigation */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Activity />Recent Signals</div>
            <span className="card-badge blue">{signalsToday} today</span>
          </div>
          <SignalFeed events={events} compact />
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title"><Brain />Latest Investigation</div>
          </div>
          <AgentTrace events={events} />
        </div>
      </div>
    </>
  );
}
