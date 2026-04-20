import { useEffect, useState } from "react";
import { DollarSign, TrendingUp, TrendingDown, Briefcase } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

type Position = {
  symbol: string; qty: number; avg_entry_price: number;
  current_price: number; unrealized_pl: number; unrealized_plpc: number; side: string;
};

type Account = {
  portfolio_value: number; cash: number; buying_power: number;
  daily_pl: number; daily_pl_pct: number;
};

type ClosedTrade = {
  id: number; symbol: string; direction: string;
  entry_price: number; exit_price: number | null;
  pnl_pct: number | null; pnl_usd: number | null;
  opened_at: string; closed_at: string | null;
};

export default function Portfolio() {
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<ClosedTrade[]>([]);

  const load = () => {
    fetch("http://localhost:8000/portfolio/state")
      .then(r => r.json())
      .then(d => { setAccount(d.account); setPositions(d.positions ?? []); })
      .catch(() => {});
    fetch("http://localhost:8000/trades/?limit=30")
      .then(r => r.json())
      .then(setTrades)
      .catch(() => {});
  };

  useEffect(() => { load(); const t = setInterval(load, 15_000); return () => clearInterval(t); }, []);

  // Build cumulative P&L curve from closed trades
  const closed = trades.filter(t => t.pnl_usd != null && t.closed_at);
  const sorted = [...closed].sort((a, b) => new Date(a.closed_at!).getTime() - new Date(b.closed_at!).getTime());
  let cumulative = 0;
  const chartData = sorted.map(t => {
    cumulative += t.pnl_usd!;
    return {
      date: new Date(t.closed_at!).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      pnl: parseFloat(cumulative.toFixed(2)),
    };
  });

  const totalPnlUsd = closed.reduce((sum, t) => sum + (t.pnl_usd ?? 0), 0);
  const wins = closed.filter(t => (t.pnl_usd ?? 0) > 0).length;
  const winRate = closed.length > 0 ? ((wins / closed.length) * 100).toFixed(0) : "—";
  const pnlColor = (account?.daily_pl ?? 0) >= 0 ? "var(--green)" : "var(--red)";

  return (
    <>
      {/* Account summary */}
      <div className="account-grid">
        <div className="stat-card">
          <div className="stat-label"><DollarSign />Portfolio Value</div>
          <div className="stat-value">{account ? `$${account.portfolio_value.toLocaleString()}` : "—"}</div>
          <div className="stat-sub">Cash: {account ? `$${account.cash.toLocaleString()}` : "—"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">
            {(account?.daily_pl ?? 0) >= 0 ? <TrendingUp /> : <TrendingDown />} Daily P&amp;L
          </div>
          <div className="stat-value" style={{ color: pnlColor }}>
            {account ? `${account.daily_pl >= 0 ? "+" : ""}$${account.daily_pl.toFixed(2)}` : "—"}
          </div>
          <div className="stat-sub" style={{ color: pnlColor }}>
            {account ? `${account.daily_pl_pct >= 0 ? "+" : ""}${(account.daily_pl_pct * 100).toFixed(3)}%` : "—"}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label"><Briefcase />Win Rate</div>
          <div className="stat-value" style={{ color: wins > 0 ? "var(--green)" : "var(--text-primary)" }}>
            {winRate}{closed.length > 0 ? "%" : ""}
          </div>
          <div className="stat-sub">{wins}W / {closed.length - wins}L — {closed.length} closed</div>
        </div>
      </div>

      {/* P&L curve */}
      {chartData.length > 1 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><TrendingUp />Cumulative P&amp;L</div>
            <span
              className="card-badge"
              style={{
                background: totalPnlUsd >= 0 ? "var(--green-dim)" : "var(--red-dim)",
                color: totalPnlUsd >= 0 ? "var(--green)" : "var(--red)",
              }}
            >
              {totalPnlUsd >= 0 ? "+" : ""}${totalPnlUsd.toFixed(2)}
            </span>
          </div>
          <div className="chart-wrap" style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={totalPnlUsd >= 0 ? "#00d084" : "#ff5163"} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={totalPnlUsd >= 0 ? "#00d084" : "#ff5163"} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} width={56} />
                <Tooltip
                  contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "var(--text-secondary)" }}
                  formatter={(v) => [`$${Number(v).toFixed(2)}`, "Cumulative P&L"]}
                />
                <Area
                  type="monotone"
                  dataKey="pnl"
                  stroke={totalPnlUsd >= 0 ? "var(--green)" : "var(--red)"}
                  strokeWidth={2}
                  fill="url(#pnlGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Open positions */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Briefcase />Open Positions</div>
          <span className="card-badge blue">{positions.length} active</span>
        </div>

        {positions.length === 0 ? (
          <div className="empty-state" style={{ padding: "32px 24px" }}>
            <Briefcase size={28} />
            <div className="empty-state-title">No open positions</div>
            <div className="empty-state-sub">Fire a signal to trigger the agent and open a trade</div>
          </div>
        ) : (
          <div className="position-list">
            {positions.map(p => {
              const pnlPos = p.unrealized_pl >= 0;
              return (
                <div key={p.symbol} className="position-card">
                  <div className="pos-symbol">{p.symbol}</div>
                  <div className={`pos-dir ${p.side === "long" ? "long" : "short"}`}>
                    {p.side.toUpperCase()}
                  </div>
                  <div className="pos-numbers">
                    <div className="pos-num">
                      <span className="pos-num-label">Qty</span>
                      <span className="pos-num-value">{p.qty}</span>
                    </div>
                    <div className="pos-num">
                      <span className="pos-num-label">Avg Entry</span>
                      <span className="pos-num-value">${p.avg_entry_price.toFixed(2)}</span>
                    </div>
                    <div className="pos-num">
                      <span className="pos-num-label">Current</span>
                      <span className="pos-num-value">${p.current_price.toFixed(2)}</span>
                    </div>
                  </div>
                  <div className={`pos-pnl ${pnlPos ? "pos" : "neg"}`}>
                    {pnlPos ? "+" : ""}${p.unrealized_pl.toFixed(2)}
                    <div style={{ fontSize: 11, fontWeight: 400, color: "var(--text-muted)", marginTop: 1 }}>
                      {pnlPos ? "+" : ""}{(p.unrealized_plpc * 100).toFixed(2)}%
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
