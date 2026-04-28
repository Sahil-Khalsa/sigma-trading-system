import { useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { WS_URL } from "./config";
import { useTheme } from "./hooks/useTheme";
import { LayoutDashboard, Radio, BarChart3, LineChart, Bell } from "lucide-react";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import Overview from "./components/Overview";
import LiveFeed from "./components/LiveFeed";
import Portfolio from "./components/Portfolio";
import TradeJournal from "./components/TradeJournal";
import Backtest from "./components/Backtest";
import Analytics from "./components/Analytics";
import Alerts from "./components/Alerts";
import "./index.css";

export type Page = "overview" | "live" | "portfolio" | "journal" | "backtest" | "analytics" | "alerts";

const MOBILE_NAV: { id: Page; label: string; icon: React.ElementType }[] = [
  { id: "overview",  label: "Home",      icon: LayoutDashboard },
  { id: "live",      label: "Live",      icon: Radio },
  { id: "portfolio", label: "Portfolio", icon: BarChart3 },
  { id: "analytics", label: "Analytics", icon: LineChart },
  { id: "alerts",    label: "Alerts",    icon: Bell },
];

export default function App() {
  const { events, connected } = useWebSocket(WS_URL);
  const [page, setPage] = useState<Page>("overview");
  const { theme, toggle } = useTheme();

  return (
    <div className="app-layout">
      <Sidebar page={page} onNav={setPage} theme={theme} onThemeToggle={toggle} />
      <div className="app-main">
        <TopBar page={page} connected={connected} />
        <div className="page-body">
          {page === "overview"   && <Overview events={events} />}
          {page === "live"       && <LiveFeed events={events} />}
          {page === "portfolio"  && <Portfolio />}
          {page === "journal"    && <TradeJournal />}
          {page === "backtest"   && <Backtest />}
          {page === "analytics"  && <Analytics />}
          {page === "alerts"     && <Alerts />}
        </div>
      </div>

      {/* Mobile bottom navigation */}
      <nav className="mobile-nav">
        {MOBILE_NAV.map(({ id, label, icon: Icon }) => (
          <div
            key={id}
            className={`mobile-nav-item ${page === id ? "active" : ""}`}
            onClick={() => setPage(id)}
          >
            <Icon />
            {label}
          </div>
        ))}
      </nav>
    </div>
  );
}
