import type { AgentStatus, ChainMessage, HealthStatus, Strategy } from "../types/agents";

interface Props {
  health: HealthStatus | null;
  agents: AgentStatus[];
  messages: ChainMessage[];
  strategies: Strategy[];
  onSpawn: (strategy: string, symbol: string, count: number) => void;
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={`text-xl font-bold mt-1 ${color ?? "text-gray-200"}`}>{value}</p>
    </div>
  );
}

export function Dashboard({ health, agents, messages, strategies, onSpawn }: Props) {
  const traders = agents.filter((a) => a.role.startsWith("trader:"));
  const totalPnl = traders.reduce((sum, a) => sum + Number(a.realized_pnl ?? 0), 0);
  const totalTrades = traders.reduce((sum, a) => sum + (a.total_trades ?? 0), 0);
  const errorCount = agents.reduce((sum, a) => sum + a.metrics.errors, 0);

  const tradeMessages = messages.filter((m) => m.type === "trade.executed");
  const errorMessages = messages.filter((m) => m.type === "error.report");
  const riskAlerts = messages.filter((m) => m.type === "risk.alert");

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            Dashboard
          </h2>
          {health && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full ${
              health.status === "online"
                ? "bg-green-900/50 text-green-400"
                : "bg-red-900/50 text-red-400"
            }`}>
              {health.status}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Active Agents" value={String(health?.agents_active ?? 0)} />
          <StatCard
            label="Total P&L"
            value={`$${totalPnl.toFixed(2)}`}
            color={totalPnl >= 0 ? "text-green-400" : "text-red-400"}
          />
          <StatCard label="Trades" value={String(totalTrades)} />
          <StatCard
            label="Errors"
            value={String(errorCount)}
            color={errorCount > 0 ? "text-red-400" : "text-gray-200"}
          />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Trade Msgs" value={String(tradeMessages.length)} color="text-green-400" />
          <StatCard label="Risk Alerts" value={String(riskAlerts.length)} color="text-red-400" />
          <StatCard label="Error Reports" value={String(errorMessages.length)} color="text-yellow-400" />
        </div>

        <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Spawn Trading Bots
          </h3>
          <div className="grid grid-cols-1 gap-2">
            {strategies.map((s) => (
              <div
                key={s.name}
                className="flex items-center justify-between bg-gray-800/50 rounded-lg px-3 py-2"
              >
                <div>
                  <p className="text-sm text-gray-200 font-medium">
                    {s.name.replace("_", " ")}
                  </p>
                  <p className="text-[10px] text-gray-500">{s.description}</p>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => onSpawn(s.name, "BTC/USDT", 1)}
                    className="px-2 py-1 text-[10px] bg-blue-900/50 text-blue-400 rounded hover:bg-blue-900 transition"
                  >
                    +1
                  </button>
                  <button
                    onClick={() => onSpawn(s.name, "BTC/USDT", 5)}
                    className="px-2 py-1 text-[10px] bg-blue-900/50 text-blue-400 rounded hover:bg-blue-900 transition"
                  >
                    +5
                  </button>
                  <button
                    onClick={() => onSpawn(s.name, "ETH/USDT", 5)}
                    className="px-2 py-1 text-[10px] bg-purple-900/50 text-purple-400 rounded hover:bg-purple-900 transition"
                  >
                    +5 ETH
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {traders.length > 0 && (
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Strategy Breakdown
            </h3>
            <div className="space-y-2">
              {Object.entries(
                traders.reduce<Record<string, { count: number; pnl: number; trades: number }>>(
                  (acc, t) => {
                    const strat = t.strategy ?? "unknown";
                    if (!acc[strat]) acc[strat] = { count: 0, pnl: 0, trades: 0 };
                    acc[strat].count++;
                    acc[strat].pnl += Number(t.realized_pnl ?? 0);
                    acc[strat].trades += t.total_trades ?? 0;
                    return acc;
                  },
                  {}
                )
              ).map(([strat, data]) => (
                <div key={strat} className="flex items-center justify-between text-xs">
                  <span className="text-gray-300">{strat.replace("_", " ")}</span>
                  <div className="flex gap-4 text-gray-500">
                    <span>{data.count} bots</span>
                    <span>{data.trades} trades</span>
                    <span className={data.pnl >= 0 ? "text-green-400" : "text-red-400"}>
                      ${data.pnl.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
