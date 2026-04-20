import { useState } from "react";
import { Brain, TrendingUp, TrendingDown, ChevronDown, ChevronUp } from "lucide-react";
import type { WSEvent } from "../hooks/useWebSocket";

type Step = { iteration: number; tool_name: string; tool_input: Record<string, unknown>; reasoning: string };

type Props = { events: WSEvent[]; showAll?: boolean };

const TOOL_COLORS: Record<string, string> = {
  get_recent_news:      "var(--blue)",
  get_signal_history:   "var(--purple)",
  get_price_context:    "var(--cyan)",
  get_earnings_calendar:"var(--yellow)",
  get_portfolio_exposure:"var(--orange)",
};

function InvestigationCard({ event }: { event: WSEvent }) {
  const [open, setOpen] = useState(false);
  const isTrade = event.type === "trade_decision";
  const d = event.data as {
    symbol: string; direction?: string; confidence?: number; thesis?: string;
    entry_price?: number; target_price?: number; stop_price?: number;
    reason?: string; steps: Step[];
  };
  const conf = d.confidence ?? 0;

  return (
    <div style={{ borderBottom: "1px solid var(--border-subtle)" }}>
      {/* Decision header */}
      <div className="decision-header">
        <div className={`decision-icon ${isTrade ? "trade" : "pass"}`}>
          {isTrade ? <TrendingUp size={20} color="var(--green)" /> : <TrendingDown size={20} color="var(--red)" />}
        </div>
        <div className="decision-meta">
          <div className="decision-title">
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 15 }}>{d.symbol}</span>
            <span className={`badge ${isTrade ? "green" : "red"}`}>
              {isTrade ? `▲ ${d.direction}` : "✕ PASS"}
            </span>
          </div>

          {isTrade && (
            <div className="confidence-bar-wrap">
              <span className="confidence-label">Confidence</span>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${conf * 100}%`,
                    background: conf >= 0.8 ? "var(--green)" : conf >= 0.7 ? "var(--yellow)" : "var(--red)",
                  }}
                />
              </div>
              <span className="confidence-value" style={{ color: conf >= 0.8 ? "var(--green)" : "var(--yellow)" }}>
                {(conf * 100).toFixed(0)}%
              </span>
            </div>
          )}

          {!isTrade && d.reason && (
            <div className="decision-thesis">{d.reason}</div>
          )}
        </div>
      </div>

      {/* Trade levels */}
      {isTrade && (
        <div className="trade-levels">
          <div className="level-chip entry">
            <span className="level-chip-label">Entry</span>
            <span className="level-chip-value">${d.entry_price?.toFixed(2)}</span>
          </div>
          <div className="level-chip target">
            <span className="level-chip-label">▲ Target</span>
            <span className="level-chip-value">${d.target_price?.toFixed(2)}</span>
          </div>
          <div className="level-chip stop">
            <span className="level-chip-label">▼ Stop</span>
            <span className="level-chip-value">${d.stop_price?.toFixed(2)}</span>
          </div>
          {d.entry_price && d.target_price && d.stop_price && (() => {
            const rr = ((d.target_price - d.entry_price) / (d.entry_price - d.stop_price));
            return (
              <div className="level-chip" style={{ borderColor: "var(--border)" }}>
                <span className="level-chip-label">R:R</span>
                <span className="level-chip-value" style={{ color: rr >= 1.5 ? "var(--green)" : "var(--yellow)" }}>
                  1:{rr.toFixed(1)}
                </span>
              </div>
            );
          })()}
        </div>
      )}

      {/* Thesis */}
      {isTrade && d.thesis && (
        <div style={{ padding: "10px 20px", borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="decision-thesis" style={{ marginTop: 0 }}>"{d.thesis}"</div>
        </div>
      )}

      {/* Steps toggle */}
      {(d.steps?.length ?? 0) > 0 && (
        <div
          style={{ padding: "10px 20px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--text-muted)" }}
          onClick={() => setOpen(o => !o)}
        >
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {d.steps.length} investigation step{d.steps.length !== 1 ? "s" : ""}
        </div>
      )}

      {open && (
        <div className="step-timeline">
          {(d.steps ?? []).map((step, i) => (
            <div key={i} className="step-row">
              <div className="step-line-wrap">
                <div className="step-num-badge">{step.iteration + 1}</div>
                {i < (d.steps.length - 1) && <div className="step-connector" />}
              </div>
              <div className="step-content">
                <div className="step-tool-name" style={{ color: TOOL_COLORS[step.tool_name] ?? "var(--purple)" }}>
                  {step.tool_name}({Object.keys(step.tool_input).join(", ")})
                </div>
                <div className="step-reasoning">{step.reasoning}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AgentTrace({ events, showAll }: Props) {
  const decisions = events.filter(e => e.type === "trade_decision" || e.type === "trade_passed");
  const shown = showAll ? decisions : decisions.slice(0, 1);

  if (shown.length === 0) {
    return (
      <div className="empty-state">
        <Brain />
        <div className="empty-state-title">No investigations yet</div>
        <div className="empty-state-sub">Agent will investigate when a signal fires</div>
      </div>
    );
  }

  return (
    <div style={{ overflowY: "auto", maxHeight: showAll ? "calc(100vh - 160px)" : undefined }}>
      {shown.map((e, i) => <InvestigationCard key={i} event={e} />)}
    </div>
  );
}
