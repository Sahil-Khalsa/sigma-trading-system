<div align="center">

# Σ SIGMA
### Production-Grade Multi-Agent AI Trading System

[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-ff6b35?style=flat-square)](https://langchain-ai.github.io/langgraph)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088ff?style=flat-square&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**SIGMA** is a real-time, autonomous AI trading system that combines rule-based signal detection with a LangGraph ReAct reasoning agent to make data-driven paper trading decisions — 24/7, fully automated.

[Features](#-features) · [Architecture](#-architecture) · [Tech Stack](#-tech-stack) · [Quick Start](#-quick-start) · [Dashboard](#-dashboard) · [Signals](#-signal-types) · [Risk Management](#-risk-management)

![SIGMA Dashboard](https://raw.githubusercontent.com/Sahil-Khalsa/sigma-trading-system/master/dashboard/src/assets/hero.png)

</div>

---

## ✨ Features

- 🤖 **Autonomous LLM Agent** — LangGraph ReAct loop investigates every signal before deciding to trade or pass
- 📡 **9 Signal Types** — RSI, Volume Surge, VWAP Breakout, MACD Crossover, Bollinger Band Squeeze, Momentum Spike, Price Breakout
- 🛡️ **8-Layer Risk Management** — Deterministic policy checks with zero LLM involvement
- ⚡ **Real-Time WebSocket** — Live signal feed, agent reasoning trace, and trade decisions pushed instantly to the dashboard
- 📊 **7-Page Dashboard** — Overview, Live Feed, Portfolio, Trade Journal, Backtest, Analytics, Alerts
- 🔔 **Notifications** — Telegram alerts + daily email digest
- 📈 **Backtest Engine** — Replay historical data through signal detector (no LLM cost)
- 🗄️ **Full Provenance** — Every agent reasoning step stored in PostgreSQL for post-trade analysis
- 🌗 **Dark / Light Mode** — Persisted per user
- 📱 **Fully Responsive** — Desktop, tablet, and mobile with bottom navigation

---

## 🏗 Architecture

```
Market Data (Alpaca WebSocket — 20 symbols)
        │
        ▼
  ┌─────────────┐
  │ PriceBuffer  │  Rolling 50-bar window per symbol
  └──────┬──────┘
         │ on every bar
         ▼
  ┌──────────────────┐
  │  SignalDetector   │  9 rule-based signals, 5-bar cooldown per symbol
  └────────┬─────────┘
           │ SignalEvent
           ▼
  ┌─────────────────────────────────────────┐
  │         Strategy Agent (LangGraph)       │
  │                                          │
  │  reason_node → tool_node → reason_node  │  ReAct loop (max 7 iterations)
  │               ↓                          │
  │         conclude_node                   │
  │                                          │
  │  Tools: news · price · signal history   │
  │          earnings · exposure · macro    │
  └──────────────┬──────────────────────────┘
                 │ TradeThesis | PassDecision
                 ▼
  ┌──────────────────────┐
  │  TradeLifecycleManager│
  │  ├─ RiskAgent (8 checks, policy.yaml)
  │  ├─ place_market_order (retry + fill confirm)
  │  └─ save_trade (PostgreSQL full trace)
  └──────────────────────┘
                 │
                 ▼
  ┌──────────────────────┐
  │   PositionMonitor     │  Trailing stop 0.5% from HWM
  │   ExitMonitor         │  Stop-loss · Take-profit · 8h time exit
  └──────────────────────┘
                 │
                 ▼
  ┌──────────────────────┐
  │  Notifications        │  Telegram (real-time) · Email digest (4:15 PM EST)
  └──────────────────────┘
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Agent Framework** | LangGraph 0.2 — ReAct state machine with typed state |
| **LLM** | GPT-4o / GPT-4o-mini via OpenAI API |
| **Backend** | FastAPI 0.115 + WebSocket broadcasting |
| **Market Data** | Alpaca WebSocket (real-time bars) + REST (historical) |
| **News & Financials** | Polygon.io |
| **Macro Context** | Fear & Greed Index (alternative.me) + SPY momentum |
| **Database** | PostgreSQL (Supabase) with psycopg2 connection pool |
| **Frontend** | React 18 + TypeScript + Vite + Recharts |
| **Styling** | Pure CSS design system — dark/light mode |
| **Notifications** | Telegram Bot API + SMTP email |
| **CI/CD** | GitHub Actions — test + build + Docker |
| **Containerization** | Docker + docker-compose |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL (or a free [Supabase](https://supabase.com) project)

### 1. Clone & Configure

```bash
git clone https://github.com/Sahil-Khalsa/sigma-trading-system.git
cd sigma-trading-system
cp .env.example .env
```

Fill in `.env` with your API keys:

```env
ALPACA_API_KEY=your_paper_trading_key
ALPACA_SECRET_KEY=your_paper_trading_secret
POLYGON_API_KEY=your_polygon_key
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://user:pass@host:5432/db

# Optional — enable notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=your@gmail.com
```

### 2. Start Backend

```bash
python -m venv venv
venv/Scripts/activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
python main.py
```

### 3. Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Open **http://localhost:5173** — the dashboard connects automatically.

### 4. Fire a Test Signal

```bash
# From the dashboard: click "Fire Signal" in the top bar
# Or via curl:
curl -X POST "http://localhost:8000/test/fire-signal?symbol=NVDA&signal_type=volume_surge&value=3.5&price=875.30"
```

Watch the agent investigate in real time on the **Live Feed** page.

### Docker (Full Stack)

```bash
docker compose up --build
# Dashboard: http://localhost
# API:       http://localhost:8000
```

---

## 📊 Dashboard

| Page | Description |
|---|---|
| **Overview** | Live stat cards, recent signals, latest agent investigation |
| **Live Feed** | Real-time signal stream + full agent reasoning trace |
| **Portfolio** | Account state, open positions, cumulative P&L chart |
| **Trade Journal** | Full trade history with expandable agent reasoning |
| **Backtest** | Run historical simulations on any symbol and date range |
| **Analytics** | Signal heatmap, P&L distribution, hourly activity, top symbols |
| **Alerts** | Real-time notification log with level filtering |

---

## 📡 Signal Types

| Signal | Trigger | Direction |
|---|---|---|
| **Volume Surge** | Volume > 2.5× 20-bar average | LONG |
| **RSI Oversold** | RSI(14) < 32 | LONG |
| **RSI Overbought** | RSI(14) > 72 | SHORT |
| **VWAP Breakout** | Price deviates > 1.5% from VWAP | LONG/SHORT |
| **Momentum Spike** | Price moves ≥ 2% in 5 bars | LONG/SHORT |
| **Price Breakout** | Close breaks 20-bar high or low | LONG/SHORT |
| **MACD Bullish** | MACD crosses above signal line | LONG |
| **MACD Bearish** | MACD crosses below signal line | SHORT |
| **BB Squeeze** | Bollinger Band width < 3% (volatility compression) | LONG |

All signals have a **5-bar cooldown** per symbol to prevent spam.

---

## 🛡 Risk Management

The `RiskAgent` runs **8 deterministic checks** (no LLM) before any trade executes:

1. **Blocked symbols** — hardcoded deny list
2. **Daily loss limit** — halt trading if portfolio down > 2%
3. **Max open positions** — no more than 5 concurrent
4. **No duplicate positions** — one position per symbol
5. **Minimum confidence** — agent must be ≥ 70% confident
6. **Reward:Risk ratio** — minimum 1.5:1
7. **Max position size** — no more than 10% of portfolio per trade
8. **Sector concentration** — no more than 40% in one sector

All thresholds are configurable in `agents/risk/policy.yaml`.

---

## 🤖 Strategy Agent Tools

The LangGraph ReAct agent has access to 6 research tools:

| Tool | Data Source |
|---|---|
| `get_recent_news` | Polygon.io news API |
| `get_price_context` | Alpaca historical OHLCV |
| `get_signal_history` | Win rate from PostgreSQL signal_stats table |
| `get_earnings_calendar` | Polygon.io financials (caution flag near earnings) |
| `get_portfolio_exposure` | Current open positions |
| `get_market_context` | Fear & Greed index + SPY momentum |

---

## 🧪 Testing

```bash
python -m pytest tests/test_e2e.py -v
```

**20 tests** — all mocked, no API keys needed. Covers:
- Signal detection + cooldown logic
- All 8 risk policy checks
- Tool type coercion and validation
- Position monitor (trailing stop + time exit)
- Full trade lifecycle (approved, blocked, qty too small, exit)
- P&L calculation accuracy
- Queue backpressure

---

## 📁 Project Structure

```
sigma/
├── agents/
│   ├── strategy/          # LangGraph ReAct agent
│   │   ├── agent.py       # State machine builder
│   │   ├── nodes.py       # reason_node, tool_node, conclude_node
│   │   ├── tools.py       # 6 research tools
│   │   ├── prompts.py     # System prompt + investigation builder
│   │   └── state.py       # TypedDict state schema
│   ├── risk/
│   │   ├── checker.py     # 8 deterministic policy checks
│   │   └── policy.yaml    # Configurable thresholds
│   └── position_monitor/  # Trailing stop + time-based exit
├── api/
│   ├── main.py            # FastAPI app + middleware
│   ├── ws_manager.py      # WebSocket broadcast manager
│   └── routes/            # trades, portfolio, analytics, backtest, ws
├── backtest/
│   └── runner.py          # Historical replay engine (no LLM)
├── dashboard/             # React + TypeScript + Vite
│   └── src/
│       ├── components/    # 10 page/feature components
│       ├── hooks/         # useWebSocket, useTheme
│       └── index.css      # Full design system
├── data/
│   └── alpaca_ws.py       # WebSocket feed + PriceBuffer
├── execution/
│   └── alpaca_client.py   # Paper trading client (paper=True enforced)
├── lifecycle/
│   └── manager.py         # Trade execution + exit monitoring
├── memory/
│   ├── trade_journal.py   # PostgreSQL operations
│   └── schema.sql         # DB schema
├── notifications/         # Telegram + email + scheduler
├── signals/
│   ├── detector.py        # 9 rule-based signal detectors
│   └── schemas.py         # SignalEvent, SignalType
├── streams/               # asyncio.Queue publisher/consumer
├── tests/
│   └── test_e2e.py        # 20 end-to-end tests
├── main.py                # System orchestrator
└── config.py              # Pydantic settings
```

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ALPACA_API_KEY` | Alpaca paper trading key | required |
| `ALPACA_SECRET_KEY` | Alpaca paper trading secret | required |
| `POLYGON_API_KEY` | Polygon.io (news, financials) | required |
| `OPENAI_API_KEY` | GPT-4o for strategy agent | required |
| `DATABASE_URL` | PostgreSQL connection string | required |
| `WATCHLIST` | Comma-separated symbols | 20 stocks |
| `MAX_POSITION_SIZE_PCT` | Max % of portfolio per trade | 0.10 |
| `MIN_CONFIDENCE_THRESHOLD` | Agent confidence floor | 0.70 |
| `MAX_AGENT_ITERATIONS` | Max ReAct loop iterations | 7 |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | optional |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID | optional |
| `SMTP_USER` | Gmail address for digest | optional |
| `SMTP_PASSWORD` | Gmail App Password | optional |

---

## 🔒 Safety

- **Paper trading enforced in code** — `paper=True` hardcoded in `execution/alpaca_client.py`, not just config
- **No real money** — all trades execute in Alpaca's paper trading environment
- **Deterministic risk checks** — risk agent uses zero LLM, fully auditable
- **`.env` in `.gitignore`** — API keys never committed

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with LangGraph · FastAPI · React · Alpaca · PostgreSQL</sub>
</div>
