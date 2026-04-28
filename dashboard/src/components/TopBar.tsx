import { useState } from "react";
import { Zap, LayoutDashboard, Radio, BarChart3, BookOpen, FlaskConical, LineChart, Bell } from "lucide-react";
import type { Page } from "../App";
import { API_URL } from "../config";

const PAGE_META: Record<Page, { label: string; icon: React.ElementType }> = {
  overview:   { label: "Overview",      icon: LayoutDashboard },
  live:       { label: "Live Feed",     icon: Radio },
  portfolio:  { label: "Portfolio",     icon: BarChart3 },
  journal:    { label: "Trade Journal", icon: BookOpen },
  backtest:   { label: "Backtest",      icon: FlaskConical },
  analytics:  { label: "Analytics",     icon: LineChart },
  alerts:     { label: "Alerts",        icon: Bell },
};

const SYMBOLS = ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","AMD","JPM","NFLX","PLTR","CRM","SNOW","UBER","COIN","SHOP","SQ","RBLX","HOOD","ARM"];
const SIGNALS = [
  "volume_surge", "rsi_oversold", "rsi_overbought",
  "vwap_breakout", "momentum_spike", "price_breakout",
  "macd_bullish", "macd_bearish", "bb_squeeze",
];
const PRICES: Record<string, number> = {
  AAPL: 182.50, MSFT: 415.20, NVDA: 875.30, TSLA: 247.80, AMZN: 198.60,
  GOOGL: 175.40, META: 558.20, AMD: 158.90, JPM: 234.50, NFLX: 645.30,
  PLTR: 38.20,  CRM: 312.80,  SNOW: 142.60, UBER: 82.40, COIN: 224.70,
  SHOP: 98.30,  SQ: 72.10,   RBLX: 42.80,  HOOD: 28.90, ARM: 132.40,
};

type Props = { page: Page; connected: boolean };

export default function TopBar({ page, connected }: Props) {
  const [symbol, setSymbol] = useState("AAPL");
  const [signal, setSignal] = useState("volume_surge");
  const [firing, setFiring] = useState(false);
  const { label, icon: Icon } = PAGE_META[page];

  const fire = async () => {
    setFiring(true);
    try {
      await fetch(
        `${API_URL}/test/fire-signal?symbol=${symbol}&signal_type=${signal}&value=3.2&price=${PRICES[symbol]}`,
        { method: "POST" }
      );
    } catch (_) { /* server may not be up during demo */ }
    setTimeout(() => setFiring(false), 2000);
  };

  return (
    <header className="topbar">
      <div className="topbar-title">
        <Icon />
        {label}
      </div>

      <div className="topbar-controls">
        <select
          className="topbar-select"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
        >
          {SYMBOLS.map(s => <option key={s}>{s}</option>)}
        </select>

        <select
          className="topbar-select"
          value={signal}
          onChange={e => setSignal(e.target.value)}
        >
          {SIGNALS.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
          ))}
        </select>

        <button className="btn btn-green" onClick={fire} disabled={firing}>
          <Zap />
          {firing ? "Firing…" : "Fire Signal"}
        </button>
      </div>

      <div className={`ws-status`}>
        <div className={`ws-dot ${connected ? "online" : "offline"}`}>
          <div className="ws-dot-ring" />
          <div className="ws-dot-inner" />
        </div>
        {connected ? "Live" : "Offline"}
      </div>
    </header>
  );
}
