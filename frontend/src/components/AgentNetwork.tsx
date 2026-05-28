import type { AgentStatus, ChainMessage } from "../types/agents";
import { AgentCard } from "./AgentCard";

interface Props {
  agents: AgentStatus[];
  messages: ChainMessage[];
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onStop: (id: string) => void;
}

export function AgentNetwork({ agents, messages, onPause, onResume, onStop }: Props) {
  const managers = agents.filter((a) =>
    ["accountant", "ops-manager", "qa-manager"].includes(a.role)
  );
  const traders = agents.filter((a) => a.role.startsWith("trader:"));
  const recentSenders = new Set(messages.slice(-20).map((m) => m.sender_id));

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2.5 border-b border-gray-700/60">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            Company Roster
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-amber-400 bg-amber-900/30 px-1.5 py-0.5 rounded">
              {managers.length} mgmt
            </span>
            <span className="text-[10px] text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded">
              {traders.length} bots
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {managers.length > 0 && (
          <div>
            <h3 className="text-[10px] uppercase text-amber-500 font-semibold mb-2 tracking-wider flex items-center gap-1.5">
              <span className="w-3 h-px bg-amber-700" />
              Management
              <span className="flex-1 h-px bg-amber-900/40" />
            </h3>
            <div className="space-y-2">
              {managers.map((a) => (
                <div
                  key={a.agent_id}
                  className={recentSenders.has(a.agent_id) ? "ring-1 ring-amber-500/20 rounded-xl" : ""}
                >
                  <AgentCard agent={a} onPause={onPause} onResume={onResume} onStop={onStop} />
                </div>
              ))}
            </div>
          </div>
        )}

        {traders.length > 0 && (
          <div>
            <h3 className="text-[10px] uppercase text-blue-500 font-semibold mb-2 tracking-wider flex items-center gap-1.5">
              <span className="w-3 h-px bg-blue-700" />
              Trading Fleet ({traders.length})
              <span className="flex-1 h-px bg-blue-900/40" />
            </h3>
            <div className="grid grid-cols-1 gap-2">
              {traders.map((a) => (
                <div
                  key={a.agent_id}
                  className={recentSenders.has(a.agent_id) ? "ring-1 ring-blue-500/20 rounded-xl" : ""}
                >
                  <AgentCard agent={a} onPause={onPause} onResume={onResume} onStop={onStop} />
                </div>
              ))}
            </div>
          </div>
        )}

        {agents.length === 0 && (
          <div className="text-center py-12">
            <p className="text-2xl mb-2">🏢</p>
            <p className="text-xs text-gray-500">No agents deployed yet</p>
            <p className="text-[10px] text-gray-600 mt-1">
              Use the Dashboard to spawn trading bots
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
