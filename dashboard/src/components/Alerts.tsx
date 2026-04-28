import { useEffect, useState } from "react";
import { Bell, CheckCircle, AlertTriangle, XCircle, Info } from "lucide-react";

import { API_URL as API } from "../config";

interface Alert {
  ts: string;
  level: "info" | "success" | "warning" | "error";
  title: string;
  body: string;
}

const ICONS: Record<string, React.ElementType> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
};

const COLORS: Record<string, string> = {
  info:    "var(--blue)",
  success: "var(--green)",
  warning: "#ffaa00",
  error:   "var(--red)",
};

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetch(`${API}/notifications/?limit=100`).then(r => r.json());
        setAlerts(Array.isArray(data) ? data : []);
      } catch (_) {}
    };
    load();
    const iv = setInterval(load, 5_000);
    return () => clearInterval(iv);
  }, []);

  const levels = ["all", "success", "error", "warning", "info"];
  const filtered = filter === "all" ? alerts : alerts.filter(a => a.level === filter);

  const counts: Record<string, number> = { all: alerts.length };
  alerts.forEach(a => { counts[a.level] = (counts[a.level] || 0) + 1; });

  return (
    <div className="alerts-page">
      <div className="alerts-header">
        <div className="alerts-title">
          <Bell size={18} />
          Notification Log
        </div>
        <div className="alerts-filter">
          {levels.map(l => (
            <button
              key={l}
              className={`filter-btn ${filter === l ? "active" : ""}`}
              style={filter === l && l !== "all" ? { borderColor: COLORS[l], color: COLORS[l] } : {}}
              onClick={() => setFilter(l)}
            >
              {l.charAt(0).toUpperCase() + l.slice(1)}
              {counts[l] ? <span className="filter-count">{counts[l]}</span> : null}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="alerts-empty">
          <Bell size={40} opacity={0.2} />
          <span>No notifications yet</span>
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Alerts appear here when signals fire, trades execute, or positions close.
          </span>
        </div>
      ) : (
        <div className="alerts-list">
          {filtered.map((a, i) => {
            const Icon = ICONS[a.level] || Info;
            const color = COLORS[a.level] || "var(--text-muted)";
            return (
              <div key={i} className="alert-item" style={{ borderLeftColor: color }}>
                <div className="alert-icon" style={{ color }}>
                  <Icon size={16} />
                </div>
                <div className="alert-content">
                  <div className="alert-title">{a.title}</div>
                  <div className="alert-body">{a.body}</div>
                </div>
                <div className="alert-time">{timeAgo(a.ts)}</div>
              </div>
            );
          })}
        </div>
      )}

      <div className="alerts-footer">
        <span>Last 100 alerts · auto-refresh every 5s</span>
        {alerts.length > 0 && (
          <span style={{ color: "var(--green)" }}>
            {counts["success"] || 0} trades · {counts["error"] || 0} errors · {counts["warning"] || 0} warnings
          </span>
        )}
      </div>
    </div>
  );
}
