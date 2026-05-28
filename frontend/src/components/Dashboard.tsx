import { useEffect, useState } from "react";
import type { AgentStatus, AIStatus, ChainMessage, HealthStatus, PortfolioSummary, Strategy } from "../types/agents";

interface Props {
  health: HealthStatus | null;
  agents: AgentStatus[];
  messages: ChainMessage[];
  strategies: Strategy[];
  onSpawn: (strategy: string, symbol: string, count: number) => void;
}

/* ────────────────────────────────────────────────────────────────────
 * Balance Widget — the centrepiece of the dashboard
 * Click to expand/collapse the P&L breakdown drawer.
 * ──────────────────────────────────────────────────────────────────── */

function BalanceWidget() {
  const [expanded, setExpanded] = useState(false);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);

  useEffect(() => {
    const load = () => {
      fetch("/api/portfolio/summary")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => d && !d.error && setPortfolio(d))
        .catch(() => {});
    };
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, []);

  const totalBalance = Number(portfolio?.total_balance_usdt ?? 0);
  const realizedPnl = Number(portfolio?.realized_pnl ?? 0);
  const unrealizedPnl = Number(portfolio?.unrealized_pnl ?? 0);
  const totalPnl = Number(portfolio?.total_pnl ?? 0);
  const totalTrades = portfolio?.total_trades ?? 0;
  const openPositions = portfolio?.open_positions ?? 0;
  const isProfit = totalPnl >= 0;
  const pctChange = totalBalance > 0 ? (totalPnl / totalBalance) * 100 : 0;
  const strategies = portfolio?.strategies ?? {};
  const balances = portfolio?.balances ?? {};

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      className={`rounded-xl border transition-all duration-300 cursor-pointer select-none ${
        expanded
          ? "bg-gray-900/80 border-gray-600/60"
          : "bg-gradient-to-br from-gray-900/90 to-gray-800/50 border-gray-700/50 hover:border-gray-600/60"
      }`}
    >
      {/* Main balance display */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <p className="text-[11px] text-gray-500 uppercase tracking-widest font-medium">
              Current Balance
            </p>
            {portfolio && (
              <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium uppercase ${
                portfolio.is_live
                  ? "bg-green-900/40 text-green-400"
                  : "bg-amber-900/30 text-amber-400"
              }`}>
                {portfolio.exchange}
              </span>
            )}
          </div>
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        <p className="text-3xl font-bold text-gray-100 tracking-tight">
          ${totalBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <div className="flex items-center gap-3 mt-2">
          <span className={`text-sm font-semibold ${isProfit ? "text-green-400" : "text-red-400"}`}>
            {isProfit ? "+" : ""}{totalPnl.toFixed(2)} USD
          </span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${
            isProfit ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"
          }`}>
            {isProfit ? "+" : ""}{pctChange.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Expanded breakdown drawer */}
      <div className={`overflow-hidden transition-all duration-300 ${
        expanded ? "max-h-[700px] opacity-100" : "max-h-0 opacity-0"
      }`}>
        <div className="border-t border-gray-700/50 px-5 py-4 space-y-4">
          {/* P&L breakdown */}
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Realized</p>
              <p className={`text-sm font-semibold mt-0.5 ${realizedPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {realizedPnl >= 0 ? "+" : ""}{realizedPnl.toFixed(2)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Unrealized</p>
              <p className={`text-sm font-semibold mt-0.5 ${unrealizedPnl >= 0 ? "text-blue-400" : "text-orange-400"}`}>
                {unrealizedPnl >= 0 ? "+" : ""}{unrealizedPnl.toFixed(2)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Open Pos.</p>
              <p className="text-sm font-semibold text-gray-300 mt-0.5">{openPositions}</p>
            </div>
          </div>

          {/* Wallet balances */}
          {Object.keys(balances).length > 0 && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 font-medium">
                Wallet
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(balances).map(([asset, amount]) => (
                  <div key={asset} className="flex justify-between bg-gray-800/30 rounded px-2.5 py-1.5 text-[11px]">
                    <span className="text-gray-400 font-medium">{asset}</span>
                    <span className="text-gray-200 tabular-nums">{Number(amount).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strategy breakdown */}
          {Object.keys(strategies).length > 0 && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 font-medium">
                P&L by Strategy
              </p>
              <div className="space-y-1.5">
                {Object.entries(strategies)
                  .sort(([, a], [, b]) => Number(b.pnl) - Number(a.pnl))
                  .map(([strat, data]) => {
                    const pnl = Number(data.pnl);
                    const stratProfit = pnl >= 0;
                    const maxPnl = Math.max(...Object.values(strategies).map((s) => Math.abs(Number(s.pnl))), 1);
                    const barWidth = Math.min((Math.abs(pnl) / maxPnl) * 100, 100);
                    return (
                      <div key={strat}>
                        <div className="flex items-center justify-between text-xs mb-0.5">
                          <span className="text-gray-300 capitalize">{strat.replace("_", " ")}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-gray-600">{data.count} bots</span>
                            <span className="text-gray-600">{data.trades} trades</span>
                            <span className={`font-medium ${stratProfit ? "text-green-400" : "text-red-400"}`}>
                              {stratProfit ? "+" : ""}${pnl.toFixed(2)}
                            </span>
                          </div>
                        </div>
                        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              stratProfit ? "bg-green-500/60" : "bg-red-500/60"
                            }`}
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {Object.keys(strategies).length === 0 && (
            <p className="text-xs text-gray-600 text-center py-2">
              No active strategies — spawn bots below to start trading
            </p>
          )}

          <p className="text-[9px] text-gray-700 text-center">
            {totalTrades} total trades / {portfolio?.active_bots ?? 0} active bots
          </p>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * Metric Pill — compact inline stat
 * ──────────────────────────────────────────────────────────────────── */

function MetricPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 bg-gray-900/60 border border-gray-700/40 rounded-lg px-3 py-2">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-bold ${color ?? "text-gray-200"}`}>{value}</span>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * AI Status Badge — shows which LLM is active
 * ──────────────────────────────────────────────────────────────────── */

function AIStatusBadge() {
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    fetch("/api/ai/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setAiStatus(d))
      .catch(() => {});
  }, []);

  if (!aiStatus) return null;

  const activeProviders = Object.values(aiStatus.providers).filter((p) => p.configured);
  const primaryProvider = aiStatus.providers[aiStatus.primary];

  return (
    <div className="bg-gray-900/60 border border-purple-700/30 rounded-lg px-3 py-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${aiStatus.available ? "bg-purple-400 animate-pulse" : "bg-gray-600"}`} />
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">AI Engine</span>
        </div>
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
          aiStatus.mode === "consensus"
            ? "bg-purple-900/50 text-purple-300"
            : aiStatus.mode === "disabled"
              ? "bg-gray-800 text-gray-500"
              : "bg-blue-900/50 text-blue-300"
        }`}>
          {aiStatus.mode}
        </span>
      </div>
      {primaryProvider && (
        <p className="text-xs text-gray-400 mt-1.5">
          <span className="text-gray-200 font-medium">{primaryProvider.display_name}</span>
          {activeProviders.length > 1 && (
            <span className="text-gray-600"> +{activeProviders.length - 1} fallback</span>
          )}
        </p>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * Spawn Panel — redesigned strategy launcher
 * ──────────────────────────────────────────────────────────────────── */

function SpawnPanel({
  strategies,
  onSpawn,
}: {
  strategies: Strategy[];
  onSpawn: (strategy: string, symbol: string, count: number) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? strategies : strategies.slice(0, 3);

  return (
    <div className="bg-gray-900/50 border border-gray-700/50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
          Deploy Bots
        </h3>
        {strategies.length > 3 && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-[10px] text-blue-400 hover:text-blue-300 transition"
          >
            {showAll ? "Show less" : `+${strategies.length - 3} more`}
          </button>
        )}
      </div>
      <div className="space-y-2">
        {visible.map((s) => (
          <div
            key={s.name}
            className="flex items-center justify-between bg-gray-800/40 rounded-lg px-3 py-2.5 hover:bg-gray-800/70 transition"
          >
            <div className="min-w-0 flex-1 mr-3">
              <p className="text-xs text-gray-200 font-medium capitalize truncate">
                {s.name.replace("_", " ")}
              </p>
              <p className="text-[10px] text-gray-500 truncate">{s.description}</p>
            </div>
            <div className="flex gap-1 shrink-0">
              <button
                onClick={() => onSpawn(s.name, "BTC/USDT", 1)}
                className="px-2 py-1.5 text-[10px] font-medium bg-blue-900/40 text-blue-400 rounded-md hover:bg-blue-800/60 transition"
                title="Spawn 1 BTC bot"
              >
                +1
              </button>
              <button
                onClick={() => onSpawn(s.name, "BTC/USDT", 5)}
                className="px-2 py-1.5 text-[10px] font-medium bg-blue-900/40 text-blue-400 rounded-md hover:bg-blue-800/60 transition"
                title="Spawn 5 BTC bots"
              >
                +5
              </button>
              <button
                onClick={() => onSpawn(s.name, "ETH/USDT", 5)}
                className="px-2 py-1.5 text-[10px] font-medium bg-purple-900/40 text-purple-400 rounded-md hover:bg-purple-800/60 transition"
                title="Spawn 5 ETH bots"
              >
                +5 ETH
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * Activity Ticker — compact recent trade list
 * ──────────────────────────────────────────────────────────────────── */

function ActivityTicker({ messages }: { messages: ChainMessage[] }) {
  const trades = messages
    .filter((m) => m.type === "trade.executed")
    .slice(-5)
    .reverse();

  if (trades.length === 0) return null;

  return (
    <div className="bg-gray-900/50 border border-gray-700/50 rounded-xl p-4">
      <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Recent Trades
      </h3>
      <div className="space-y-1.5">
        {trades.map((t) => {
          const p = t.payload;
          const isBuy = p.side === "buy";
          const pnl = Number(p.pnl ?? 0);
          return (
            <div key={t.id} className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isBuy ? "bg-green-500" : "bg-red-500"}`} />
                <span className="text-gray-400">
                  <span className={`font-medium ${isBuy ? "text-green-400" : "text-red-400"}`}>
                    {String(p.side).toUpperCase()}
                  </span>
                  {" "}{String(p.quantity)} {String(p.symbol)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-gray-500">@{String(p.filled_price)}</span>
                {pnl !== 0 && (
                  <span className={pnl >= 0 ? "text-green-400" : "text-red-400"}>
                    {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * Main Dashboard Export
 * ──────────────────────────────────────────────────────────────────── */

export function Dashboard({ health, agents, messages, strategies, onSpawn }: Props) {
  const traders = agents.filter((a) => a.role.startsWith("trader:"));
  const totalTrades = traders.reduce((sum, a) => sum + (a.total_trades ?? 0), 0);
  const errorCount = agents.reduce((sum, a) => sum + a.metrics.errors, 0);
  const riskAlerts = messages.filter((m) => m.type === "risk.alert");

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-700/60">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            Dashboard
          </h2>
          {health && (
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${
                health.status === "online" ? "bg-green-500" : "bg-red-500"
              }`} />
              <span className="text-[10px] text-gray-500">{health.status}</span>
            </div>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Clickable Balance Widget — fetches real data from /api/portfolio/summary */}
        <BalanceWidget />

        {/* Quick metrics row */}
        <div className="grid grid-cols-2 gap-2">
          <MetricPill label="Agents" value={String(health?.agents_active ?? 0)} />
          <MetricPill
            label="Trades"
            value={String(totalTrades)}
            color={totalTrades > 0 ? "text-blue-400" : "text-gray-200"}
          />
          <MetricPill
            label="Alerts"
            value={String(riskAlerts.length)}
            color={riskAlerts.length > 0 ? "text-red-400" : "text-gray-200"}
          />
          <MetricPill
            label="Errors"
            value={String(errorCount)}
            color={errorCount > 0 ? "text-red-400" : "text-gray-200"}
          />
        </div>

        {/* AI Status */}
        <AIStatusBadge />

        {/* Recent trades ticker */}
        <ActivityTicker messages={messages} />

        {/* Spawn panel */}
        <SpawnPanel strategies={strategies} onSpawn={onSpawn} />
      </div>
    </div>
  );
}
