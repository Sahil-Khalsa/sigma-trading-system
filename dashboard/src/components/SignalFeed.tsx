import type { WSEvent } from "../hooks/useWebSocket";
import { Activity } from "lucide-react";

type Props = { events: WSEvent[]; compact?: boolean };

const SIG_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  volume_surge:   { bg: "var(--yellow-dim)", color: "var(--yellow)", label: "Vol Surge" },
  rsi_oversold:   { bg: "var(--green-dim)",  color: "var(--green)",  label: "RSI OS" },
  rsi_overbought: { bg: "var(--red-dim)",    color: "var(--red)",    label: "RSI OB" },
  vwap_breakout:  { bg: "var(--blue-dim)",   color: "var(--blue)",   label: "VWAP BK" },
  price_breakout: { bg: "var(--purple-dim)", color: "var(--purple)", label: "Price BK" },
  momentum_spike: { bg: "var(--yellow-dim)", color: "var(--orange)", label: "Momentum" },
};

export default function SignalFeed({ events, compact }: Props) {
  const signals = events.filter(e => e.type === "signal_fired");
  const shown = compact ? signals.slice(0, 8) : signals;

  if (shown.length === 0) {
    return (
      <div className="empty-state">
        <Activity />
        <div className="empty-state-title">No signals yet</div>
        <div className="empty-state-sub">Use "Fire Signal" in the toolbar to inject a test signal</div>
      </div>
    );
  }

  return (
    <div className="signal-list">
      {shown.map((e, i) => {
        const d = e.data as {
          symbol: string; signal_type: string; value: number;
          price: number; fired_at: string;
        };
        const s = SIG_STYLE[d.signal_type] ?? { bg: "var(--bg-elevated)", color: "var(--text-muted)", label: d.signal_type };
        const time = new Date(d.fired_at).toLocaleTimeString("en-US", { hour12: false });

        return (
          <div key={i} className="signal-item">
            <div className="signal-dot" style={{ background: s.color }} />
            <span className="signal-symbol">{d.symbol}</span>
            <span
              className="signal-type-pill"
              style={{ background: s.bg, color: s.color }}
            >
              {s.label}
            </span>
            <span className="signal-value">×{d.value.toFixed(2)}</span>
            <span className="signal-price">${d.price.toFixed(2)}</span>
            <span className="signal-time">{time}</span>
          </div>
        );
      })}
    </div>
  );
}
