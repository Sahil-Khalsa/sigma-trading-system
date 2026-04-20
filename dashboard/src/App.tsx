import { useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
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

export default function App() {
  const { events, connected } = useWebSocket("ws://localhost:8000/ws");
  const [page, setPage] = useState<Page>("overview");

  return (
    <div className="app-layout">
      <Sidebar page={page} onNav={setPage} />
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
    </div>
  );
}
