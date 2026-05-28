import type { AgentStatus } from "../types/agents";

const STATUS_STYLES: Record<string, { dot: string; bg: string }> = {
  running: { dot: "bg-green-500", bg: "bg-green-900/20" },
  paused: { dot: "bg-yellow-500", bg: "bg-yellow-900/20" },
  stopped: { dot: "bg-gray-500", bg: "bg-gray-800/30" },
  error: { dot: "bg-red-500", bg: "bg-red-900/20" },
  idle: { dot: "bg-blue-500", bg: "bg-blue-900/20" },
};

const ROLE_ICONS: Record<string, string> = {
  accountant: "📊",
  "ops-manager": "🏗",
  "qa-manager": "🔍",
};

function getRoleIcon(role: string): string {
  if (role.startsWith("trader:")) return "🤖";
  return ROLE_ICONS[role] ?? "⚡";
}

interface Props {
  agent: AgentStatus;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onStop: (id: string) => void;
}

export function AgentCard({ agent, onPause, onResume, onStop }: Props) {
  const isTrader = agent.role.startsWith("trader:");
  const isManager = ["accountant", "ops-manager", "qa-manager"].includes(agent.role);
  const style = STATUS_STYLES[agent.status] ?? STATUS_STYLES.idle;
  const pnl = Number(agent.realized_pnl ?? 0);
  const strategyLabel = agent.strategy?.replace("_", " ") ?? agent.role;

  return (
    <div
      className={`rounded-xl border p-3 transition-all ${
        isManager
          ? "border-amber-700/40 bg-amber-950/10"
          : "border-gray-700/40 bg-gray-900/40"
      } hover:border-gray-600/60`}
    >
      {/* Top row: identity + status */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base shrink-0">{getRoleIcon(agent.role)}</span>
          <div className="min-w-0">
            <p className="font-semibold text-gray-200 text-xs truncate">{agent.agent_id}</p>
            <p className="text-gray-500 text-[10px] uppercase tracking-wider capitalize">
              {strategyLabel}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${style.bg} text-gray-400`}>
            {agent.status}
          </span>
        </div>
      </div>

      {/* Trader-specific metrics */}
      {isTrader && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] mb-2.5 bg-gray-800/30 rounded-lg px-2.5 py-2">
          <div className="flex justify-between">
            <span className="text-gray-500">Symbol</span>
            <span className="text-gray-200 font-medium">{agent.symbol}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Position</span>
            <span className={`font-medium ${
              Number(agent.position ?? 0) !== 0 ? "text-blue-400" : "text-gray-400"
            }`}>{agent.position}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">P&L</span>
            <span className={`font-medium ${pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Trades</span>
            <span className="text-gray-200 font-medium">{agent.total_trades ?? 0}</span>
          </div>
        </div>
      )}

      {/* Footer: cycles + controls */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-gray-600">
          {agent.metrics.cycles} cycles / {agent.metrics.messages_sent} msgs
        </span>
        {!isManager && (
          <div className="flex gap-1">
            {agent.status === "running" ? (
              <button
                onClick={() => onPause(agent.agent_id)}
                className="px-2 py-1 text-[10px] font-medium bg-yellow-900/30 text-yellow-400 rounded-md hover:bg-yellow-900/50 transition"
              >
                Pause
              </button>
            ) : agent.status === "paused" ? (
              <button
                onClick={() => onResume(agent.agent_id)}
                className="px-2 py-1 text-[10px] font-medium bg-green-900/30 text-green-400 rounded-md hover:bg-green-900/50 transition"
              >
                Resume
              </button>
            ) : null}
            <button
              onClick={() => onStop(agent.agent_id)}
              className="px-2 py-1 text-[10px] font-medium bg-red-900/30 text-red-400 rounded-md hover:bg-red-900/50 transition"
            >
              Stop
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
