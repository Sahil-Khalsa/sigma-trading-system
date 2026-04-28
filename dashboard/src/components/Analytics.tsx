import { useEffect, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";

import { API_URL as API } from "../config";

interface Summary {
  total_trades: number;
  winning_trades: number;
  win_rate_pct: number;
  total_pnl_usd: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  avg_confidence: number;
}

interface HeatmapRow { symbol: string; signal_type: string; win_rate_pct: number; total_trades: number; avg_pnl_pct: number }
interface PnlRow { id: number; symbol: string; direction: string; pnl_usd: number; pnl_pct: number; closed_at: string; confidence: number }
interface HourRow { hour: number; signal_type: string; count: number }
interface SymbolRow { symbol: string; total_trades: number; wins: number; total_pnl_usd: number }

const SIGNAL_TYPES = ["volume_surge", "rsi_oversold", "rsi_overbought", "vwap_breakout"];
const SIGNAL_SHORT: Record<string, string> = {
  volume_surge: "Vol", rsi_oversold: "RSI↓", rsi_overbought: "RSI↑", vwap_breakout: "VWAP",
};

function winRateColor(rate: number | undefined): string {
  if (rate === undefined || rate === null) return "var(--bg-surface)";
  if (rate >= 70) return "rgba(0,208,132,0.55)";
  if (rate >= 50) return "rgba(0,208,132,0.25)";
  if (rate >= 30) return "rgba(255,170,0,0.25)";
  return "rgba(255,77,77,0.3)";
}

function fmt(n: number, decimals = 2) {
  return n?.toFixed(decimals) ?? "—";
}

export default function Analytics() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapRow[]>([]);
  const [pnlData, setPnlData] = useState<PnlRow[]>([]);
  const [hourly, setHourly] = useState<HourRow[]>([]);
  const [symbols, setSymbols] = useState<SymbolRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, h, p, ho, sy] = await Promise.all([
          fetch(`${API}/analytics/summary`).then(r => r.json()),
          fetch(`${API}/analytics/signal-heatmap`).then(r => r.json()),
          fetch(`${API}/analytics/pnl-timeline?limit=100`).then(r => r.json()),
          fetch(`${API}/analytics/hourly-activity`).then(r => r.json()),
          fetch(`${API}/analytics/top-symbols`).then(r => r.json()),
        ]);
        setSummary(s);
        setHeatmap(Array.isArray(h) ? h : []);
        setPnlData(Array.isArray(p) ? p : []);
        setHourly(Array.isArray(ho) ? ho : []);
        setSymbols(Array.isArray(sy) ? sy : []);
      } catch (_) {}
      setLoading(false);
    };
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, []);

  // Build heatmap grid: symbols × signal_types
  const hmSymbols = [...new Set(heatmap.map(r => r.symbol))].sort();
  const hmMap: Record<string, Record<string, HeatmapRow>> = {};
  heatmap.forEach(r => {
    if (!hmMap[r.symbol]) hmMap[r.symbol] = {};
    hmMap[r.symbol][r.signal_type] = r;
  });

  // Build hourly totals by hour (0-23)
  const hourTotals: Record<number, number> = {};
  hourly.forEach(r => { hourTotals[r.hour] = (hourTotals[r.hour] || 0) + Number(r.count); });
  const hourChartData = Array.from({ length: 24 }, (_, h) => ({
    hour: `${String(h).padStart(2, "0")}:00`,
    count: hourTotals[h] || 0,
  }));

  // Cumulative P&L for the AreaChart
  let running = 0;
  const cumulativePnl = pnlData.map(t => {
    running += Number(t.pnl_usd) || 0;
    return {
      label: `#${t.id}`,
      cumulative: parseFloat(running.toFixed(2)),
      pnl: parseFloat(Number(t.pnl_usd).toFixed(2)),
      symbol: t.symbol,
    };
  });

  if (loading) return (
    <div className="analytics-loading">
      <div className="spinner" />
      <span>Loading analytics…</span>
    </div>
  );

  return (
    <div className="analytics-page">
      {/* ── Summary Cards ── */}
      <div className="stat-grid" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Total Trades</div>
          <div className="stat-value">{summary?.total_trades ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Win Rate</div>
          <div className="stat-value" style={{ color: "var(--green)" }}>
            {summary?.win_rate_pct ?? 0}%
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Net P&amp;L</div>
          <div className="stat-value" style={{ color: (summary?.total_pnl_usd ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
            {(summary?.total_pnl_usd ?? 0) >= 0 ? "+" : ""}${fmt(summary?.total_pnl_usd ?? 0)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Confidence</div>
          <div className="stat-value" style={{ color: "var(--purple)" }}>
            {((summary?.avg_confidence ?? 0) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="analytics-grid">
        {/* ── Chart 1: Cumulative P&L Curve ── */}
        <div className="chart-card chart-wide">
          <div className="chart-card-header">
            <span className="chart-card-title">Cumulative P&amp;L</span>
            <span className="chart-card-sub">{pnlData.length} closed trades</span>
          </div>
          {cumulativePnl.length === 0 ? (
            <div className="chart-empty">No closed trades yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={cumulativePnl} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d084" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00d084" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="label" tick={{ fill: "#475569", fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fill: "#475569", fontSize: 10 }} tickFormatter={v => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#0f1117", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [`$${Number(v).toFixed(2)}`, "Cumulative P&L"]}
                />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
                <Area type="monotone" dataKey="cumulative" stroke="#00d084" strokeWidth={2} fill="url(#pnlGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ── Chart 2: Per-Trade P&L Bars ── */}
        <div className="chart-card chart-wide">
          <div className="chart-card-header">
            <span className="chart-card-title">Per-Trade P&amp;L</span>
            <span className="chart-card-sub">green = win · red = loss</span>
          </div>
          {pnlData.length === 0 ? (
            <div className="chart-empty">No closed trades yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={pnlData.slice(-50)} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="symbol" tick={{ fill: "#475569", fontSize: 10 }} />
                <YAxis tick={{ fill: "#475569", fontSize: 10 }} tickFormatter={v => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#0f1117", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [`$${Number(v).toFixed(2)}`, "P&L"]}
                />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
                <Bar dataKey="pnl_usd" radius={[3, 3, 0, 0]}>
                  {pnlData.slice(-50).map((t, i) => (
                    <Cell key={i} fill={Number(t.pnl_usd) >= 0 ? "#00d084" : "#ff4d4d"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ── Chart 3: Signal Performance Heatmap ── */}
        <div className="chart-card chart-wide">
          <div className="chart-card-header">
            <span className="chart-card-title">Signal Win Rate Heatmap</span>
            <span className="chart-card-sub">symbol × signal type</span>
          </div>
          {hmSymbols.length === 0 ? (
            <div className="chart-empty">No signal stats yet</div>
          ) : (
            <div className="heatmap-table-wrap">
              <table className="heatmap-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    {SIGNAL_TYPES.map(st => <th key={st}>{SIGNAL_SHORT[st]}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {hmSymbols.map(sym => (
                    <tr key={sym}>
                      <td className="heatmap-sym">{sym}</td>
                      {SIGNAL_TYPES.map(st => {
                        const cell = hmMap[sym]?.[st];
                        return (
                          <td
                            key={st}
                            className="heatmap-cell"
                            style={{ background: winRateColor(cell?.win_rate_pct) }}
                            title={cell ? `${cell.total_trades} trades · ${cell.win_rate_pct}% WR · avg P&L ${cell.avg_pnl_pct?.toFixed(3)}%` : "No data"}
                          >
                            {cell ? `${cell.win_rate_pct}%` : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Chart 4: Hourly Activity ── */}
        <div className="chart-card">
          <div className="chart-card-header">
            <span className="chart-card-title">Hourly Signal Activity</span>
            <span className="chart-card-sub">EST · last 30 days</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={hourChartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="hour" tick={{ fill: "#475569", fontSize: 9 }} interval={2} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#0f1117", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                formatter={(v) => [Number(v), "Signals"]}
              />
              <Bar dataKey="count" fill="#a78bfa" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* ── Chart 5: Top Symbols P&L ── */}
        <div className="chart-card">
          <div className="chart-card-header">
            <span className="chart-card-title">Top Symbols by P&amp;L</span>
            <span className="chart-card-sub">all-time net</span>
          </div>
          {symbols.length === 0 ? (
            <div className="chart-empty">No closed trades yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={symbols.slice(0, 10)}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis type="number" tick={{ fill: "#475569", fontSize: 10 }} tickFormatter={v => `$${v}`} />
                <YAxis type="category" dataKey="symbol" tick={{ fill: "#94a3b8", fontSize: 11 }} width={44} />
                <Tooltip
                  contentStyle={{ background: "#0f1117", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [`$${Number(v).toFixed(2)}`, "Net P&L"]}
                />
                <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" />
                <Bar dataKey="total_pnl_usd" radius={[0, 3, 3, 0]}>
                  {symbols.slice(0, 10).map((s, i) => (
                    <Cell key={i} fill={Number(s.total_pnl_usd) >= 0 ? "#00d084" : "#ff4d4d"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
