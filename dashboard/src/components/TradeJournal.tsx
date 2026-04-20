import { useEffect, useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, TrendingUp } from "lucide-react";

type Step = { iteration: number; tool_name: string; reasoning: string };

type Trade = {
  id: number; symbol: string; direction: string; status: string;
  entry_price: number; exit_price: number | null;
  pnl_pct: number | null; pnl_usd: number | null;
  confidence: number; risk_check_result: string;
  opened_at: string; thesis: string;
};

type Investigation = {
  thesis: string;
  investigation_steps: Step[];
};

export default function TradeJournal() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/trades/?limit=50")
      .then(r => r.json())
      .then(setTrades)
      .catch(() => {});
  }, []);

  const toggleTrace = async (id: number) => {
    if (expanded === id) { setExpanded(null); setInvestigation(null); return; }
    try {
      const res = await fetch(`http://localhost:8000/trades/${id}/investigation`);
      const data = await res.json();
      setInvestigation(data);
      setExpanded(id);
    } catch (_) {
      setExpanded(id);
      setInvestigation(null);
    }
  };

  // Summary stats
  const approved = trades.filter(t => t.risk_check_result === "APPROVED");
  const closed = approved.filter(t => t.status === "CLOSED");
  const wins = closed.filter(t => (t.pnl_pct ?? 0) > 0).length;
  const winRate = closed.length > 0 ? ((wins / closed.length) * 100).toFixed(0) : "—";
  const avgPnl = closed.length > 0
    ? ((closed.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) / closed.length) * 100).toFixed(2)
    : "—";
  const totalPnlUsd = closed.reduce((s, t) => s + (t.pnl_usd ?? 0), 0);

  return (
    <div className="card">
      {/* Summary stats */}
      <div className="journal-stats">
        <div className="journal-stat">
          <div className="stat-label"><BookOpen />Total Trades</div>
          <div className="stat-value" style={{ fontSize: 22 }}>{trades.length}</div>
          <div className="stat-sub">{approved.length} executed</div>
        </div>
        <div className="journal-stat">
          <div className="stat-label"><TrendingUp />Win Rate</div>
          <div className="stat-value" style={{ fontSize: 22, color: wins > 0 ? "var(--green)" : undefined }}>
            {winRate}{closed.length > 0 ? "%" : ""}
          </div>
          <div className="stat-sub">{wins}W · {closed.length - wins}L</div>
        </div>
        <div className="journal-stat">
          <div className="stat-label">Avg P&amp;L</div>
          <div className="stat-value" style={{ fontSize: 22, color: parseFloat(avgPnl) >= 0 ? "var(--green)" : "var(--red)" }}>
            {avgPnl !== "—" ? `${parseFloat(avgPnl) >= 0 ? "+" : ""}${avgPnl}%` : "—"}
          </div>
          <div className="stat-sub">per trade</div>
        </div>
        <div className="journal-stat">
          <div className="stat-label">Total P&amp;L</div>
          <div className="stat-value" style={{ fontSize: 22, color: totalPnlUsd >= 0 ? "var(--green)" : "var(--red)" }}>
            {totalPnlUsd !== 0 ? `${totalPnlUsd >= 0 ? "+" : ""}$${totalPnlUsd.toFixed(2)}` : "$0.00"}
          </div>
          <div className="stat-sub">realized</div>
        </div>
      </div>

      {/* Table */}
      {trades.length === 0 ? (
        <div className="empty-state">
          <BookOpen />
          <div className="empty-state-title">No trades recorded</div>
          <div className="empty-state-sub">Trades appear here after the agent investigates a signal</div>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="trade-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Direction</th>
                <th>Status</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&amp;L %</th>
                <th>P&amp;L $</th>
                <th>Confidence</th>
                <th>Risk</th>
                <th>Opened</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
              {trades.map(t => {
                const pnlPos = (t.pnl_pct ?? 0) >= 0;
                const isExp = expanded === t.id;
                return (
                  <>
                    <tr key={t.id} className={isExp ? "expanded" : ""} onClick={() => toggleTrace(t.id)}>
                      <td className="sym-cell">{t.symbol}</td>
                      <td>
                        <span className={`badge ${t.direction === "LONG" ? "green" : "red"}`}>
                          {t.direction === "LONG" ? "▲" : "▼"} {t.direction}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${t.status === "OPEN" ? "blue" : "muted"}`}>
                          {t.status}
                        </span>
                      </td>
                      <td className="mono">${t.entry_price?.toFixed(2)}</td>
                      <td className="mono">{t.exit_price ? `$${t.exit_price.toFixed(2)}` : "—"}</td>
                      <td className={t.pnl_pct !== null ? (pnlPos ? "profit" : "loss") : ""}>
                        {t.pnl_pct !== null ? `${pnlPos ? "+" : ""}${(t.pnl_pct * 100).toFixed(2)}%` : "—"}
                      </td>
                      <td className={t.pnl_usd !== null ? (pnlPos ? "profit" : "loss") : ""}>
                        {t.pnl_usd !== null ? `${pnlPos ? "+" : ""}$${t.pnl_usd.toFixed(2)}` : "—"}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <div style={{ width: 40, height: 4, background: "var(--bg-overlay)", borderRadius: 2, overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: `${t.confidence * 100}%`,
                              background: t.confidence >= 0.8 ? "var(--green)" : t.confidence >= 0.7 ? "var(--yellow)" : "var(--red)",
                              borderRadius: 2,
                            }} />
                          </div>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                            {(t.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${t.risk_check_result === "APPROVED" ? "green" : "red"}`}>
                          {t.risk_check_result}
                        </span>
                      </td>
                      <td style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                        {new Date(t.opened_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td onClick={e => { e.stopPropagation(); toggleTrace(t.id); }}>
                        <button className={`trace-toggle ${isExp ? "open" : ""}`}>
                          {isExp ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      </td>
                    </tr>

                    {isExp && (
                      <tr key={`exp-${t.id}`}>
                        <td colSpan={11} style={{ padding: 0 }}>
                          <div className="investigation-expand">
                            {investigation?.thesis && (
                              <div className="investigation-thesis">"{investigation.thesis}"</div>
                            )}
                            {(investigation?.investigation_steps ?? []).length > 0 && (
                              <div className="step-timeline" style={{ padding: 0 }}>
                                {investigation!.investigation_steps.map((s, i) => (
                                  <div key={i} className="step-row">
                                    <div className="step-line-wrap">
                                      <div className="step-num-badge">{s.iteration + 1}</div>
                                      {i < investigation!.investigation_steps.length - 1 && <div className="step-connector" />}
                                    </div>
                                    <div className="step-content">
                                      <div className="step-tool-name">{s.tool_name}</div>
                                      <div className="step-reasoning">{s.reasoning}</div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
