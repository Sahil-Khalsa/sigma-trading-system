<div align="center">

# Σ SIGMA
### Autonomous Multi-Agent AI Trading System

<p>
  <img src="https://img.shields.io/badge/Python-3.12-3776ab?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61dafb?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178c6?style=for-the-badge&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-ReAct_Agent-ff6b35?style=for-the-badge" />
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-20_Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-2088ff?style=for-the-badge&logo=githubactions&logoColor=white" />
</p>

**SIGMA** is a full-stack, production-grade autonomous trading system that monitors 20 stocks in real time, detects technical signals, and routes them through a LangGraph ReAct AI agent that *reasons* about each opportunity before deciding to trade — with a live React dashboard showing every decision as it happens.

> Built end-to-end with real API integrations, a normalized PostgreSQL schema, WebSocket broadcasting, CI/CD pipelines, and Docker deployment. Not a tutorial — a complete system.

[Architecture](#-system-architecture) · [Demo](#-dashboard-pages) · [AI Agent](#-the-ai-brain-langgraph-react-agent) · [Signals](#-signal-detection-engine) · [Risk](#-risk-management) · [Quick Start](#-quick-start)

</div>

---

## What Makes This Different

Most trading bots are 30 lines of Python: *"if RSI < 30, buy."* SIGMA is a different class of system.

| Typical Bot | SIGMA |
|---|---|
| Hard-coded if/else rules | LLM reasons about *why* a signal matters |
| No explanation of decisions | Full reasoning trace stored in PostgreSQL |
| Script that crashes silently | Async event pipeline with backpressure + graceful shutdown |
| No risk controls | 8-layer deterministic risk agent blocks bad trades |
| Terminal output | Real-time dashboard with 7 pages and live WebSocket updates |
| No tests | 20 unit tests, zero API keys needed |
| No deployment story | Docker Compose + Nginx + GitHub Actions CI |

---

## System Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                     SIGMA — Data Flow                                ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Alpaca REST API (5s poll)                                           ║
║  20 symbols × OHLCV bars                                            ║
║         │                                                            ║
║         ▼                                                            ║
║  ┌─────────────────────┐                                             ║
║  │   Signal Detector    │  9 pattern checks per bar (pure math)      ║
║  │   (signals/detector) │  RSI · Volume · MACD · BB · VWAP · more   ║
║  └──────────┬──────────┘  5-min cooldown per symbol per signal type  ║
║             │ SignalEvent                                             ║
║             ▼                                                        ║
║  ┌──────────────────────────────────────────────────────────┐       ║
║  │              Strategy Agent  (LangGraph ReAct)            │       ║
║  │                                                            │       ║
║  │   reason_node ──► tool_node ──► reason_node (loops)       │       ║
║  │         │               ▲                                  │       ║
║  │         └──► conclude_node (BUY / SKIP + confidence)      │       ║
║  │                                                            │       ║
║  │   Tools available to the agent:                           │       ║
║  │   • get_recent_news       (Polygon.io)                    │       ║
║  │   • get_price_context     (Alpaca historical)             │       ║
║  │   • get_signal_history    (Win rate from PostgreSQL)      │       ║
║  │   • get_earnings_calendar (Polygon.io financials)         │       ║
║  │   • get_portfolio_exposure(Current open positions)        │       ║
║  │   • get_market_context    (Fear & Greed + SPY momentum)   │       ║
║  └───────────────────────────┬──────────────────────────────┘       ║
║                               │ TradeThesis (BUY) | PassDecision     ║
║                               ▼                                      ║
║  ┌────────────────────────────────────────────────────────┐         ║
║  │              Risk Agent  (Deterministic — NO LLM)       │         ║
║  │   8 hard policy checks: loss limits · position caps ·   │         ║
║  │   sector concentration · confidence floor · R:R ratio   │         ║
║  └───────────────────────────┬────────────────────────────┘         ║
║                               │ APPROVED / BLOCKED                   ║
║                               ▼                                      ║
║  ┌────────────────────────────────────────────────────────┐         ║
║  │   Execution Layer  (Alpaca Paper Trading API)           │         ║
║  │   Market order → fill confirmation → save to DB         │         ║
║  └───────────────────────────┬────────────────────────────┘         ║
║                               │                                      ║
║                               ▼                                      ║
║  ┌──────────────────────────────────────────────────────┐           ║
║  │   Position & Exit Monitor  (runs every 30s)           │           ║
║  │   Trailing stop (0.5% from HWM) · Stop-loss ·         │           ║
║  │   Take-profit · 8-hour forced exit                     │           ║
║  └───────────────────────────┬──────────────────────────┘           ║
║                               │                                      ║
║              ┌────────────────┼────────────────┐                    ║
║              ▼                ▼                ▼                    ║
║         PostgreSQL      WebSocket          Notifications            ║
║         (full trace)    (React dashboard)  (Telegram + Email)       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

Everything runs in **one Python process** via `asyncio.gather()` — no Redis, no Celery, no microservices. Five long-lived coroutines cooperate on a single event loop.

---

## The AI Brain — LangGraph ReAct Agent

This is the core differentiator. When a signal fires, the system doesn't blindly trade — it invokes a **LangGraph ReAct state machine** backed by an LLM.

### How the Agent Thinks

```
User fires signal: NVDA volume_surge @ $875.30
      │
      ▼
reason_node: "Volume surge detected on NVDA. Let me check news first."
      │  calls get_recent_news("NVDA")
      ▼
tool_node: returns Polygon news → "NVDA beat earnings estimates by 12%"
      │
      ▼
reason_node: "News is very bullish. Let me check current market mood."
      │  calls get_market_context()
      ▼
tool_node: returns Fear & Greed = 71 (Greed), SPY +0.8% today
      │
      ▼
reason_node: "Strong confirmation across signals. Checking our exposure."
      │  calls get_portfolio_exposure()
      ▼
tool_node: returns 2 open positions, both different sectors
      │
      ▼
conclude_node: BUY — confidence 0.82
      reasoning: "Volume surge corroborated by earnings beat + greed market.
                  Low portfolio risk, no sector concentration issue."
```

### Agent Engineering Details

| Property | Value |
|---|---|
| Framework | LangGraph 0.2 (StateGraph with typed nodes) |
| State | `StrategyAgentState` TypedDict — persists across all nodes |
| Loop control | Hard cap at 6 tool calls/invocation — prevents runaway LLM cost |
| Output | Structured `TradeThesis(action, confidence, reasoning, stop_loss, take_profit)` |
| Auditability | Full message history + tool outputs saved to PostgreSQL per trade |
| Cost guard | Budget cap means each decision costs ~$0.01-0.02 max |

---

## Signal Detection Engine

**9 patterns detected in pure Python** — no pandas-ta, no external libraries. Built on rolling deques for O(1) updates.

| Signal | Logic | Direction |
|---|---|---|
| **Volume Surge** | `current_vol > 2.5 × avg_20_bar_vol` | LONG |
| **RSI Oversold** | `RSI(14) < 32` | LONG |
| **RSI Overbought** | `RSI(14) > 72` | SHORT |
| **VWAP Breakout** | `abs(price - vwap) / vwap > 0.015` | LONG / SHORT |
| **Momentum Spike** | `abs(price_change_5_bars) >= 0.02` | LONG / SHORT |
| **Price Breakout** | `close > max(close[-20:])` or `close < min(close[-20:])` | LONG / SHORT |
| **MACD Bullish Cross** | MACD crosses above signal line (EMA 12/26/9) | LONG |
| **MACD Bearish Cross** | MACD crosses below signal line | SHORT |
| **BB Squeeze** | `(upper_band - lower_band) / middle_band < 0.03` | LONG |

**Cooldown system**: each `(symbol, signal_type)` pair is locked for 5 minutes after firing — prevents duplicate signals on volatile bars.

**Buffer minimum**: MACD requires 26 bars of history. Detector refuses to evaluate until the buffer is deep enough.

---

## Risk Management

The `RiskAgent` runs **before every trade execution** — 8 deterministic checks, zero LLM involvement. If any check fails, the trade is blocked and the reason is logged.

```
✓  1. Symbol not on blocked list
✓  2. Daily loss < 2% of starting equity          (halts all trading if breached)
✓  3. Open positions < 5
✓  4. No existing position in this symbol
✓  5. Agent confidence ≥ 0.70
✓  6. Reward:Risk ratio ≥ 1.5
✓  7. Position size ≤ 10% of portfolio value
✓  8. Sector concentration ≤ 40%
```

All thresholds live in `agents/risk/policy.yaml` — adjustable without touching code.

**Why no LLM in risk?** Risk decisions must be auditable, reproducible, and fast. An LLM could argue its way past a stop-loss rule on a bad day. Deterministic code cannot.

---

## Dashboard Pages

A 7-page React 18 dashboard with real-time WebSocket updates. Every trade, signal, and agent decision appears within milliseconds.

| Page | What You See |
|---|---|
| **Overview** | Live stat cards (today's trades, win rate, P&L), recent signals, latest agent investigation with reasoning |
| **Live Feed** | Scrolling real-time stream of every signal fired + full agent reasoning trace (expandable) |
| **Portfolio** | Current open positions, account equity, cumulative P&L area chart |
| **Trade Journal** | Complete history of every trade — entry, exit, P&L, agent confidence, full reasoning |
| **Backtest** | Run any symbol on any date range through the signal engine. See equity curve + trade log |
| **Analytics** | 5 charts: P&L timeline, per-trade bar chart, signal heatmap (win rate by type), hourly activity, top symbols |
| **Alerts** | Notification log with level filters (success / warning / error / info), auto-refreshes every 5s |

### UI Engineering

- **Real-time updates** via `useWebSocket` hook — maintains a 200-event circular buffer, no polling
- **Dark / Light mode** — CSS variable design system, toggled with `data-theme` attribute on `<html>`, persisted in `localStorage`
- **Fully responsive** — 3 breakpoints (900px tablet, 600px mobile, 480px small mobile), mobile bottom navigation for thumb reach
- **Zero UI framework** — pure CSS design system with variables for spacing, color, and typography

---

## Backend Architecture

### FastAPI + WebSocket Broadcasting

```python
# Five coroutines running cooperatively on one event loop
await asyncio.gather(
    signal_loop(),           # polls Alpaca every 5s, detects signals
    lifecycle_manager.run(), # routes signals → agent → risk → execution
    position_monitor.run(),  # checks open positions every 30s for exits
    websocket_broadcaster(), # drains event queue, fans out to all clients
    run_daily_scheduler(),   # sends 4:15 PM EST digest email
)
```

### Event Pipeline

```
signal fires → asyncio.Queue(maxsize=100) → WebSocketManager.broadcast()
                     │                              │
               backpressure:              all connected clients
               drop if full              get the event instantly
               (protects producer)       (WebSocket, not polling)
```

### Database Schema (PostgreSQL / Supabase)

```sql
symbols          — watchlist (20 rows)
signals          — every signal that ever fired (append-only)
trades           — full trade record: entry/exit/PnL/agent reasoning
signal_stats     — aggregated win rate per signal type (rebuilt nightly)
portfolio_snapshots — equity curve sampled every 15 minutes
```

Every query uses **parameterized SQL** (`%s` placeholders) and `RealDictCursor` — rows return as dicts, serialized directly to JSON with zero transformation.

DB access is via `psycopg2.ThreadedConnectionPool(minconn=2, maxconn=10)` bridged to async via `asyncio.to_thread()`.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Agent Framework** | LangGraph 0.2 | Typed state machine — debuggable, not a black box |
| **LLM** | GPT-4o-mini (OpenAI) | Cost-efficient reasoning with structured output |
| **Backend** | FastAPI 0.115 | Async-native, built-in WebSocket, automatic OpenAPI docs |
| **Market Data** | Alpaca REST + WebSocket | Paper trading API + real-time bars |
| **News & Financials** | Polygon.io | News feed + earnings calendar |
| **Macro Context** | Fear & Greed API + SPY momentum | Free, no-key, fast signal |
| **Database** | PostgreSQL on Supabase | Managed, free tier, real Postgres |
| **ORM** | Raw psycopg2 + ThreadedConnectionPool | No ORM overhead, full SQL control |
| **Frontend** | React 18 + TypeScript + Vite | Fast dev, type-safe, modern toolchain |
| **Charts** | Recharts | Composable, React-native charting |
| **Notifications** | Telegram Bot API + SMTP/Gmail | Real-time phone alerts + daily digest |
| **Containerization** | Docker + docker-compose | One-command full-stack deployment |
| **CI/CD** | GitHub Actions | Tests + build on every push |
| **Reverse Proxy** | Nginx | Serves built React app + proxies /api |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- A free [Supabase](https://supabase.com) project (PostgreSQL)
- [Alpaca paper trading account](https://alpaca.markets) (free)
- OpenAI API key

### 1. Clone & Configure

```bash
git clone https://github.com/Sahil-Khalsa/sigma-trading-system.git
cd sigma-trading-system
cp .env.example .env
```

Fill in `.env`:

```env
# Required
ALPACA_API_KEY=your_paper_trading_key
ALPACA_SECRET_KEY=your_paper_trading_secret
POLYGON_API_KEY=your_polygon_key
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://user:pass@host:5432/postgres

# Optional — real phone/email notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_gmail_app_password
NOTIFICATION_EMAIL=your@gmail.com
```

### 2. Run Backend

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt
python main.py
# API running at http://localhost:8000
```

### 3. Run Dashboard

```bash
cd dashboard
npm install
npm run dev
# Dashboard at http://localhost:5173
```

### 4. Fire a Test Signal

```bash
curl -X POST "http://localhost:8000/test/fire-signal?symbol=NVDA&signal_type=volume_surge&value=3.5&price=875.30"
```

Watch the agent investigate live on the **Live Feed** page.

### Docker (Full Stack — One Command)

```bash
docker compose up --build
# Dashboard: http://localhost
# API:       http://localhost:8000/docs
```

---

## Testing

```bash
python -m pytest tests/test_e2e.py -v
```

**20 tests — all pass — zero API keys needed** (all external calls are mocked).

| Test Suite | What's Covered |
|---|---|
| Signal Detection | RSI calculation accuracy, cooldown enforcement |
| Risk Agent | All 8 policy checks independently validated |
| Tool Execution | Type coercion, unknown tool handling, invalid inputs |
| Position Monitor | Trailing stop math, 8-hour time exit logic |
| Trade Lifecycle | Approved trade flow, risk-blocked flow, qty-too-small edge case |
| PnL Calculation | Multi-unit position exit math verified |
| Queue Backpressure | `QueueFull` drop behavior under load |
| Agent State | Initial state schema validation |

---

## Project Structure

```
sigma/
├── agents/
│   ├── strategy/
│   │   ├── agent.py       # LangGraph StateGraph builder
│   │   ├── nodes.py       # reason_node, tool_node, conclude_node
│   │   ├── tools.py       # 6 callable research tools
│   │   ├── prompts.py     # System prompt + investigation builder
│   │   └── state.py       # StrategyAgentState TypedDict
│   ├── risk/
│   │   ├── checker.py     # 8 deterministic policy checks
│   │   └── policy.yaml    # All thresholds (configurable)
│   └── position_monitor/  # Trailing stop + time-based exit
│
├── api/
│   ├── main.py            # FastAPI app + CORS + middleware
│   ├── ws_manager.py      # WebSocket client set + broadcast
│   └── routes/            # analytics, portfolio, trades, backtest,
│                          # notifications, test, ws
├── backtest/
│   └── runner.py          # Historical replay (no LLM, fast)
│
├── dashboard/             # React 18 + TypeScript + Vite
│   └── src/
│       ├── components/    # Overview, LiveFeed, Portfolio, TradeJournal,
│       │                  # Backtest, Analytics, Alerts, Sidebar, TopBar
│       ├── hooks/
│       │   ├── useWebSocket.ts   # 200-event circular buffer
│       │   └── useTheme.ts       # dark/light with localStorage
│       └── index.css      # Full CSS variable design system
│
├── data/
│   └── alpaca_ws.py       # PriceBuffer + real-time bar feed
├── execution/
│   └── alpaca_client.py   # Paper trading (paper=True hardcoded)
├── lifecycle/
│   └── manager.py         # Signal → agent → risk → execute → persist
├── memory/
│   ├── trade_journal.py   # All PostgreSQL read/write operations
│   └── schema.sql         # Full DB schema
├── notifications/
│   ├── service.py         # Central dispatcher (Telegram + SMTP + log)
│   ├── telegram.py        # Async Telegram Bot API (aiohttp)
│   ├── email_notifier.py  # SMTP/TLS email sender
│   └── scheduler.py       # 4:15 PM EST daily digest
├── signals/
│   ├── detector.py        # 9 signal detectors (pure Python math)
│   └── schemas.py         # SignalEvent, SignalType enum
├── streams/
│   ├── publisher.py       # asyncio.Queue publisher with backpressure
│   └── consumer.py        # Serial signal consumer
├── tests/
│   └── test_e2e.py        # 20 tests, fully mocked
│
├── main.py                # System entry point — asyncio.gather() orchestrator
├── config.py              # Pydantic settings (reads from .env)
├── requirements.txt
├── Dockerfile             # Multi-stage Python backend image
├── dashboard/Dockerfile   # Vite build → Nginx static serve
└── docker-compose.yml     # Full stack orchestration
```

---

## Safety Design

| Property | Implementation |
|---|---|
| **Paper trading enforced in code** | `paper=True` hardcoded in `alpaca_client.py` — not a config flag |
| **No real money risk** | All trades execute in Alpaca's sandbox environment |
| **Deterministic risk gate** | Risk agent uses zero LLM — auditable, predictable, fast |
| **Idempotent orders** | `client_order_id = f"{signal_id}-{timestamp}"` — broker rejects duplicates on crash/restart |
| **Graceful shutdown** | SIGINT/SIGTERM handlers cancel all coroutines, close DB pool, send WebSocket close frames |
| **API keys protected** | `.env` in `.gitignore` — never committed |

---

## Key Engineering Decisions

**1. LangGraph over raw tool-use loops**
LangGraph gives explicit state management and typed transitions. When something goes wrong, you can see exactly which node failed and what state it was in. Raw loops are opaque.

**2. Deterministic risk — no LLM**
The risk agent is pure code. An LLM can rationalize anything; risk rules must be absolute. Separating subjective reasoning (strategy agent) from non-negotiable constraints (risk agent) is the key architectural insight.

**3. asyncio.Queue over Redis**
Zero external dependency for the signal pipeline. Redis would add infrastructure overhead for a problem an in-process queue solves completely — as long as we're single-process, which we are.

**4. 6 tool-call budget cap**
Without a hard cap, the agent can loop on edge cases and burn $10 in API costs on one signal. The cap is the difference between a $5/month system and a $500/month system.

**5. Pure Python signal math over pandas-ta**
Pandas-ta adds a 50MB dependency and makes tests harder (real DataFrames required). Rolling deques with manual math are 10 lines, fully testable with mocked data, and faster for 20-bar windows.

---

## CI/CD Pipeline

GitHub Actions runs on every push to `master`:

```yaml
1. Backend Tests    → pytest (20 tests, PostgreSQL service container)
2. Dashboard Build  → TypeScript check + Vite production build
3. Docker Build     → Validates both images compile cleanly
```

---

## Author

**Sahil Khalsa** — [GitHub](https://github.com/Sahil-Khalsa)

Built from scratch as a full-stack AI engineering project demonstrating: autonomous agent design, real-time event pipelines, production React dashboards, and end-to-end system integration.

---

<div align="center">
  <sub>
    Python · FastAPI · LangGraph · OpenAI · React · TypeScript · PostgreSQL · WebSockets · Docker · Alpaca · Polygon.io
  </sub>
</div>
