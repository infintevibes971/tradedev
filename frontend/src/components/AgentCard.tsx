import type { AgentStatus } from "../types/agents";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-green-500",
  paused: "bg-yellow-500",
  stopped: "bg-gray-500",
  error: "bg-red-500",
  idle: "bg-blue-500",
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

function getRoleLabel(agent: AgentStatus): string {
  if (agent.strategy) return agent.strategy.replace("_", " ");
  return agent.role;
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

  return (
    <div
      className={`rounded-lg border p-3 text-sm ${
        isManager
          ? "border-amber-700/50 bg-amber-950/20"
          : "border-gray-700/50 bg-gray-900/50"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{getRoleIcon(agent.role)}</span>
          <div>
            <p className="font-semibold text-gray-200 text-xs">{agent.agent_id}</p>
            <p className="text-gray-500 text-[10px] uppercase">{getRoleLabel(agent)}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[agent.status]}`} />
          <span className="text-[10px] text-gray-500">{agent.status}</span>
        </div>
      </div>

      {isTrader && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-gray-400 mb-2">
          <span>Symbol: <span className="text-gray-200">{agent.symbol}</span></span>
          <span>Position: <span className="text-gray-200">{agent.position}</span></span>
          <span>P&L: <span className={
            Number(agent.realized_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400"
          }>{agent.realized_pnl}</span></span>
          <span>Trades: <span className="text-gray-200">{agent.total_trades}</span></span>
        </div>
      )}

      <div className="flex items-center justify-between text-[10px] text-gray-500">
        <span>Cycles: {agent.metrics.cycles} | Msgs: {agent.metrics.messages_sent}</span>
        {!isManager && (
          <div className="flex gap-1">
            {agent.status === "running" ? (
              <button
                onClick={() => onPause(agent.agent_id)}
                className="px-1.5 py-0.5 bg-yellow-900/50 text-yellow-400 rounded hover:bg-yellow-900 transition"
              >
                Pause
              </button>
            ) : agent.status === "paused" ? (
              <button
                onClick={() => onResume(agent.agent_id)}
                className="px-1.5 py-0.5 bg-green-900/50 text-green-400 rounded hover:bg-green-900 transition"
              >
                Resume
              </button>
            ) : null}
            <button
              onClick={() => onStop(agent.agent_id)}
              className="px-1.5 py-0.5 bg-red-900/50 text-red-400 rounded hover:bg-red-900 transition"
            >
              Stop
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
