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

  const recentSenders = new Set(
    messages.slice(-20).map((m) => m.sender_id)
  );

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-gray-700">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Company Roster
        </h2>
        <p className="text-[10px] text-gray-500 mt-0.5">
          {managers.length} managers · {traders.length} traders
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {managers.length > 0 && (
          <div>
            <h3 className="text-[10px] uppercase text-amber-500 font-semibold mb-2 tracking-wider">
              Management
            </h3>
            <div className="space-y-2">
              {managers.map((a) => (
                <div
                  key={a.agent_id}
                  className={recentSenders.has(a.agent_id) ? "ring-1 ring-amber-500/30 rounded-lg" : ""}
                >
                  <AgentCard agent={a} onPause={onPause} onResume={onResume} onStop={onStop} />
                </div>
              ))}
            </div>
          </div>
        )}

        {traders.length > 0 && (
          <div>
            <h3 className="text-[10px] uppercase text-blue-500 font-semibold mb-2 tracking-wider">
              Trading Fleet ({traders.length})
            </h3>
            <div className="grid grid-cols-1 gap-2">
              {traders.map((a) => (
                <div
                  key={a.agent_id}
                  className={recentSenders.has(a.agent_id) ? "ring-1 ring-blue-500/30 rounded-lg" : ""}
                >
                  <AgentCard agent={a} onPause={onPause} onResume={onResume} onStop={onStop} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
