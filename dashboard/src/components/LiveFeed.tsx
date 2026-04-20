import { Activity, Brain } from "lucide-react";
import type { WSEvent } from "../hooks/useWebSocket";
import SignalFeed from "./SignalFeed";
import AgentTrace from "./AgentTrace";

type Props = { events: WSEvent[] };

export default function LiveFeed({ events }: Props) {
  const signalCount = events.filter(e => e.type === "signal_fired").length;
  const decisionCount = events.filter(
    e => e.type === "trade_decision" || e.type === "trade_passed"
  ).length;

  return (
    <div className="grid-2" style={{ flex: 1, alignItems: "start" }}>
      <div className="card" style={{ display: "flex", flexDirection: "column" }}>
        <div className="card-header">
          <div className="card-title"><Activity />Signal Stream</div>
          <span className="card-badge blue">{signalCount} events</span>
        </div>
        <SignalFeed events={events} />
      </div>

      <div className="card" style={{ display: "flex", flexDirection: "column" }}>
        <div className="card-header">
          <div className="card-title"><Brain />Agent Investigations</div>
          <span className="card-badge purple">{decisionCount} decisions</span>
        </div>
        <AgentTrace events={events} showAll />
      </div>
    </div>
  );
}
