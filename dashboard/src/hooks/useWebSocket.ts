import { useEffect, useRef, useState, useCallback } from "react";

export type WSEvent = {
  type:
    | "signal_fired"
    | "investigation_started"
    | "trade_decision"
    | "trade_passed";
  data: Record<string, unknown>;
};

export function useWebSocket(url: string) {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    ws.current = new WebSocket(url);

    ws.current.onopen = () => setConnected(true);
    ws.current.onclose = () => {
      setConnected(false);
      setTimeout(connect, 3000); // auto-reconnect
    };
    ws.current.onerror = () => ws.current?.close();
    ws.current.onmessage = (e) => {
      const event: WSEvent = JSON.parse(e.data);
      setEvents((prev) => [event, ...prev].slice(0, 100)); // keep last 100
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => ws.current?.close();
  }, [connect]);

  return { events, connected };
}
