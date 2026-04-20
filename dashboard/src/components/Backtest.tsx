import { useState } from "react";
import { FlaskConical, Play, TrendingUp, BarChart2 } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from "recharts";

const SYMBOLS = ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","AMD","JPM","NFLX","PLTR","CRM","COIN","UBER"];

type Trade = {
  direction: string; entry_price: number; exit_price: number | null;
  pnl_pct: number | null; pnl_usd: number | null; exit_reason: string | null;
  entry_time: string; exit_time: string | null;
};

type Result = {
  symbol: string; start_date: string; end_date: string;
  total_bars: number; total_signals: number; total_trades: number;
  wins: number; losses: number; win_rate: number;
  avg_pnl_pct: number; gross_pnl_pct: number; profit_factor: number;
  trades: Trade[];
};

export default function Backtest() {
  const [symbol, setSymbol] = useState("AAPL");
  const [startDate, setStartDate] = useState("2024-10-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true); setResult(null); setError(null);
    try {
      const res = await fetch("http://localhost:8000/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, start_date: startDate, end_date: endDate }),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail ?? "Backtest failed");
      }
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // Build cumulative P&L curve
  let cumPnl = 0;
  const chartData = (result?.trades ?? [])
    .filter(t => t.pnl_pct !== null)
    .map((t, i) => {
      cumPnl += (t.pnl_pct ?? 0) * 100;
      return { trade: i + 1, pnl: parseFloat(cumPnl.toFixed(3)) };
    });

  const isProfit = (result?.gross_pnl_pct ?? 0) >= 0;

  return (
    <>
      {/* Config card */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><FlaskConical />Backtest Configuration</div>
          <span className="card-badge muted">Rule-based · No LLM cost</span>
        </div>
        <div className="card-body" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Symbol</label>
            <select className="topbar-select" style={{ padding: "8px 12px" }} value={symbol} onChange={e => setSymbol(e.target.value)}>
              {SYMBOLS.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Start Date</label>
            <input
              type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", padding: "8px 12px", borderRadius: "var(--radius)", fontSize: 13, fontFamily: "var(--font-sans)", outline: "none" }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>End Date</label>
            <input
              type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", padding: "8px 12px", borderRadius: "var(--radius)", fontSize: 13, fontFamily: "var(--font-sans)", outline: "none" }}
            />
          </div>
          <button className="btn btn-green" onClick={run} disabled={loading} style={{ alignSelf: "flex-end" }}>
            <Play size={13} />
            {loading ? "Running…" : "Run Backtest"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: "var(--red-dim)", border: "1px solid var(--red-border)", borderRadius: "var(--radius-lg)", padding: "14px 18px", color: "var(--red)", fontSize: 13 }}>
          {error}
        </div>
      )}

      {loading && (
        <div className="empty-state">
          <div style={{ width: 32, height: 32, border: "3px solid var(--border)", borderTopColor: "var(--green)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          <div className="empty-state-title">Fetching historical bars…</div>
          <div className="empty-state-sub">Replaying signals through detector — this may take 10–30s</div>
        </div>
      )}

      {result && (
        <>
          {/* Stats */}
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-label"><BarChart2 />Total Trades</div>
              <div className="stat-value">{result.total_trades}</div>
              <div className="stat-sub">{result.total_signals} signals detected</div>
            </div>
            <div className="stat-card">
              <div className="stat-label"><TrendingUp />Win Rate</div>
              <div className="stat-value" style={{ color: result.win_rate >= 0.5 ? "var(--green)" : "var(--red)" }}>
                {(result.win_rate * 100).toFixed(1)}%
              </div>
              <div className="stat-sub">{result.wins}W · {result.losses}L</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Gross P&amp;L</div>
              <div className="stat-value" style={{ color: isProfit ? "var(--green)" : "var(--red)" }}>
                {isProfit ? "+" : ""}{(result.gross_pnl_pct * 100).toFixed(2)}%
              </div>
              <div className="stat-sub">Avg {(result.avg_pnl_pct * 100).toFixed(3)}% / trade</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Profit Factor</div>
              <div className="stat-value" style={{ color: result.profit_factor >= 1.5 ? "var(--green)" : result.profit_factor >= 1 ? "var(--yellow)" : "var(--red)" }}>
                {result.profit_factor === Infinity ? "∞" : result.profit_factor.toFixed(2)}
              </div>
              <div className="stat-sub">gross win / gross loss</div>
            </div>
          </div>

          {/* Equity curve */}
          {chartData.length > 1 && (
            <div className="card">
              <div className="card-header">
                <div className="card-title"><TrendingUp />Equity Curve</div>
                <span className="card-badge muted">{result.symbol} · {result.start_date} → {result.end_date}</span>
              </div>
              <div className="chart-wrap" style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="btGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={isProfit ? "#00d084" : "#ff5163"} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={isProfit ? "#00d084" : "#ff5163"} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="trade" label={{ value: "Trade #", position: "insideBottom", offset: -2, fill: "var(--text-muted)", fontSize: 11 }} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} width={50} />
                    <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 2" />
                    <Tooltip
                      contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                      formatter={(v) => [`${Number(v).toFixed(3)}%`, "Cumulative P&L"]}
                    />
                    <Area type="monotone" dataKey="pnl" stroke={isProfit ? "var(--green)" : "var(--red)"} strokeWidth={2} fill="url(#btGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Trade list */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><BarChart2 />Trade Log</div>
              <span className="card-badge blue">{result.trades.length} trades</span>
            </div>
            <div className="table-wrap">
              <table className="trade-table">
                <thead>
                  <tr>
                    <th>#</th><th>Direction</th><th>Entry</th><th>Exit</th>
                    <th>P&amp;L %</th><th>P&amp;L $</th><th>Exit Reason</th><th>Entry Time</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => {
                    const pos = (t.pnl_pct ?? 0) >= 0;
                    return (
                      <tr key={i}>
                        <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{i + 1}</td>
                        <td><span className={`badge ${t.direction === "LONG" ? "green" : "red"}`}>{t.direction === "LONG" ? "▲" : "▼"} {t.direction}</span></td>
                        <td className="mono">${t.entry_price.toFixed(2)}</td>
                        <td className="mono">{t.exit_price ? `$${t.exit_price.toFixed(2)}` : "—"}</td>
                        <td className={pos ? "profit" : "loss"}>{t.pnl_pct !== null ? `${pos ? "+" : ""}${(t.pnl_pct * 100).toFixed(3)}%` : "—"}</td>
                        <td className={pos ? "profit" : "loss"}>{t.pnl_usd !== null ? `${pos ? "+" : ""}$${t.pnl_usd.toFixed(2)}` : "—"}</td>
                        <td><span className={`badge ${t.exit_reason === "take_profit" ? "green" : t.exit_reason === "stop_loss" ? "red" : "muted"}`}>{t.exit_reason ?? "—"}</span></td>
                        <td style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{t.entry_time ? new Date(t.entry_time).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
