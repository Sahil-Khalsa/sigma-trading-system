import { LayoutDashboard, Radio, BarChart3, BookOpen, FlaskConical, LineChart, Bell } from "lucide-react";
import type { Page } from "../App";

type Props = { page: Page; onNav: (p: Page) => void };

const NAV = [
  { id: "overview",   label: "Overview",      icon: LayoutDashboard },
  { id: "live",       label: "Live Feed",     icon: Radio },
  { id: "portfolio",  label: "Portfolio",     icon: BarChart3 },
  { id: "journal",    label: "Trade Journal", icon: BookOpen },
  { id: "backtest",   label: "Backtest",      icon: FlaskConical },
  { id: "analytics",  label: "Analytics",     icon: LineChart },
  { id: "alerts",     label: "Alerts",        icon: Bell },
] as const;

export default function Sidebar({ page, onNav }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">Σ</div>
        <div className="sidebar-logo-text">
          <span className="sidebar-logo-name">SIGMA</span>
          <span className="sidebar-logo-sub">Multi-Agent AI</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {NAV.map(({ id, label, icon: Icon }) => (
          <div
            key={id}
            className={`nav-item ${page === id ? "active" : ""}`}
            onClick={() => onNav(id as Page)}
          >
            <Icon />
            {label}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-badge">
          <div className="sidebar-badge-dot" />
          Paper Trading Mode
        </div>
        <div className="sidebar-badge">
          <svg width="7" height="7" viewBox="0 0 7 7" fill="none">
            <circle cx="3.5" cy="3.5" r="3.5" fill="#4a5568" />
          </svg>
          20 symbols · paper mode
        </div>
      </div>
    </aside>
  );
}
