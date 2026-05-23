# TradeDev — Multi-Agent AI Trading Company

## Project Overview
A ChatDev-inspired multi-agent trading platform where specialized AI agents collaborate
as an "Expert Algorithmic Trading Company." Agents communicate via a structured TradeChain
messaging system, execute trades on paper/live exchanges, and learn from shared experience.

## Tech Stack

### Backend
- **Language:** Python 3.12+ (async-first)
- **Framework:** FastAPI with Uvicorn (ASGI)
- **Async:** asyncio for concurrent bot execution (50+ simultaneous agents)
- **WebSockets:** FastAPI WebSocket endpoints for real-time UI streaming
- **LLM:** Anthropic Claude SDK (`anthropic`) for agent decision-making
- **Exchange:** `ccxt` for unified exchange API (Binance, Alpaca, etc.)
- **Encryption:** `cryptography.fernet` for API key vault

### Frontend
- **Framework:** React 18+ with TypeScript
- **Build:** Vite
- **Styling:** Tailwind CSS
- **Real-time:** Native WebSocket API for agent message streaming
- **Visualization:** D3.js or React Flow for agent network graph

### Data
- **Primary DB:** SQLite (dev) / PostgreSQL (prod) via SQLAlchemy + Alembic
- **Vector DB:** ChromaDB for Experience Pool (co-learning)
- **Cache:** In-memory dict (dev) / Redis (prod)

### Testing
- **Backend:** pytest + pytest-asyncio
- **Frontend:** Vitest + React Testing Library
- **E2E:** Playwright (Phase 7)

## Directory Structure
```
tradedev/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── config.py                # Settings & env vars
│   │   ├── models/                  # SQLAlchemy models
│   │   │   ├── user.py              # User profile & encrypted API keys
│   │   │   └── trade.py             # Trade history records
│   │   ├── agents/
│   │   │   ├── base.py              # Abstract Agent base class
│   │   │   ├── factory.py           # Agent Factory (spawn/configure bots)
│   │   │   ├── registry.py          # Live agent registry & lifecycle
│   │   │   ├── traders/             # Trading bot implementations
│   │   │   │   ├── mean_reversion.py
│   │   │   │   ├── momentum.py
│   │   │   │   ├── arbitrage.py
│   │   │   │   ├── sentiment.py
│   │   │   │   └── grid.py
│   │   │   ├── accountant.py        # P&L, drawdown, weekly reports
│   │   │   ├── ops_manager.py       # Capital allocation, rate limits
│   │   │   └── qa_manager.py        # Error interception, auto-patching
│   │   ├── chain/
│   │   │   ├── tradechain.py        # Message bus (pub/sub + routing)
│   │   │   └── messages.py          # Typed message schemas
│   │   ├── exchange/
│   │   │   ├── adapter.py           # Abstract exchange interface
│   │   │   ├── mock.py              # Paper trading adapter
│   │   │   └── live.py              # Live ccxt adapter
│   │   ├── security/
│   │   │   ├── vault.py             # API key encrypt/decrypt
│   │   │   └── auth.py              # User authentication
│   │   ├── experience/
│   │   │   └── pool.py              # ChromaDB vector store for co-learning
│   │   ├── websocket/
│   │   │   └── manager.py           # WS connection manager for UI
│   │   └── api/
│   │       ├── routes_users.py      # User CRUD + key management
│   │       ├── routes_agents.py     # Agent spawn/stop/status
│   │       ├── routes_trades.py     # Trade history & reports
│   │       └── routes_ws.py         # WebSocket endpoints
│   ├── alembic/                     # DB migrations
│   ├── tests/
│   │   ├── test_agents.py
│   │   ├── test_chain.py
│   │   ├── test_exchange.py
│   │   └── test_security.py
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── AgentNetwork.tsx      # ChatDev-style agent visualizer
│   │   │   ├── MessageFeed.tsx       # Live agent conversation log
│   │   │   ├── Dashboard.tsx         # P&L, portfolio overview
│   │   │   ├── AgentCard.tsx         # Individual agent status card
│   │   │   └── KeyVault.tsx          # API key management UI
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts       # WS connection hook
│   │   └── types/
│   │       └── agents.ts             # Shared TypeScript types
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── CLAUDE.md
├── .env.example
└── .gitignore
```

## Database Schema

### users
| Column       | Type         | Notes                          |
|-------------|-------------|--------------------------------|
| id          | UUID (PK)   | Auto-generated                 |
| username    | VARCHAR(50)  | Unique                         |
| email       | VARCHAR(255) | Unique                         |
| password_hash | VARCHAR(255) | bcrypt hashed                |
| created_at  | TIMESTAMP    | Default NOW()                  |

### api_keys
| Column       | Type         | Notes                          |
|-------------|-------------|--------------------------------|
| id          | UUID (PK)   | Auto-generated                 |
| user_id     | UUID (FK)    | References users.id            |
| exchange    | VARCHAR(50)  | e.g. "binance", "alpaca"       |
| api_key_enc | BYTEA        | Fernet-encrypted API key       |
| api_secret_enc | BYTEA     | Fernet-encrypted API secret    |
| is_paper    | BOOLEAN      | True = testnet/paper trading   |
| created_at  | TIMESTAMP    | Default NOW()                  |

### trades
| Column       | Type         | Notes                          |
|-------------|-------------|--------------------------------|
| id          | UUID (PK)   | Auto-generated                 |
| agent_id    | VARCHAR(100) | Which bot placed this trade    |
| user_id     | UUID (FK)    | References users.id            |
| exchange    | VARCHAR(50)  |                                |
| symbol      | VARCHAR(20)  | e.g. "BTC/USDT"               |
| side        | VARCHAR(4)   | "buy" or "sell"                |
| quantity    | DECIMAL      |                                |
| price       | DECIMAL      |                                |
| status      | VARCHAR(20)  | "open", "filled", "cancelled"  |
| pnl         | DECIMAL      | Realized P&L for closed trades |
| timestamp   | TIMESTAMP    |                                |

## Code Conventions
- **Formatting:** `ruff` for linting/formatting (line length 100)
- **Type hints:** Required on all function signatures
- **Async:** All I/O-bound functions must be `async`
- **Naming:** snake_case for Python, camelCase for TypeScript
- **Imports:** Group as stdlib → third-party → local, separated by blank lines
- **Error handling:** Never swallow exceptions silently; log + re-raise or handle
- **Agents:** All agents inherit from `BaseAgent` and implement `async def execute()`
- **Messages:** All inter-agent messages use Pydantic models from `chain/messages.py`

## Commands
```bash
# Backend
cd backend && pip install -r requirements.txt    # Install deps
cd backend && uvicorn app.main:app --reload      # Dev server (port 8000)
cd backend && pytest tests/ -v                   # Run tests
cd backend && ruff check app/                    # Lint
cd backend && ruff format app/                   # Format

# Frontend
cd frontend && npm install                       # Install deps
cd frontend && npm run dev                       # Dev server (port 5173)
cd frontend && npm run build                     # Production build
cd frontend && npm test                          # Run tests

# Database
cd backend && alembic upgrade head               # Run migrations
cd backend && alembic revision --autogenerate -m "description"  # New migration
```

## Environment Variables
```
ANTHROPIC_API_KEY=          # Claude API key for agent LLM calls
DATABASE_URL=sqlite:///./tradedev.db
ENCRYPTION_KEY=             # Fernet key for API key vault (auto-generated if missing)
REDIS_URL=                  # Optional, for production caching
LOG_LEVEL=INFO
```

## Safety Rules
- NEVER store plaintext API keys — always Fernet-encrypt at rest
- NEVER execute live trades without explicit user confirmation
- Paper trading mode is the DEFAULT; live trading requires opt-in
- All exchange API calls go through the adapter layer (never call ccxt directly)
- Rate-limit all exchange API calls (managed by Ops Manager agent)
- The QA Manager agent must validate every trade before execution
