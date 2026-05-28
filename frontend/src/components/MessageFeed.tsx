import { useEffect, useRef } from "react";
import type { ChainMessage } from "../types/agents";

const TYPE_STYLES: Record<string, { color: string; icon: string; bg: string }> = {
  "trade.executed": { color: "text-green-400", icon: "⬆", bg: "bg-green-900/10" },
  "trade.request": { color: "text-blue-400", icon: "📋", bg: "bg-blue-900/10" },
  "trade.rejected": { color: "text-red-400", icon: "✕", bg: "bg-red-900/10" },
  "risk.alert": { color: "text-red-500 font-semibold", icon: "⚠", bg: "bg-red-900/20" },
  "capital.request": { color: "text-yellow-400", icon: "💰", bg: "" },
  "capital.response": { color: "text-yellow-300", icon: "✓", bg: "" },
  "status.report": { color: "text-gray-400", icon: "📊", bg: "" },
  "error.report": { color: "text-red-400", icon: "✕", bg: "bg-red-900/10" },
  "agent.chat": { color: "text-cyan-400", icon: "💬", bg: "" },
  "system.command": { color: "text-purple-400", icon: "⚙", bg: "" },
  "report.weekly": { color: "text-amber-400", icon: "📈", bg: "" },
};

function formatPayload(msg: ChainMessage): string {
  const p = msg.payload;
  switch (msg.type) {
    case "trade.executed":
      return `${p.side} ${p.quantity} ${p.symbol} @ ${p.filled_price} (P&L: ${p.pnl})`;
    case "risk.alert":
      return `${p.alert}: ${p.agent_id} lost ${p.pnl} on ${p.symbol}`;
    case "capital.request":
      return `Requesting ${p.amount} capital`;
    case "capital.response":
      return p.approved ? `Approved: ${p.amount}` : `Denied: ${p.reason}`;
    case "error.report":
      return `${p.agent_id}: ${p.error}`;
    case "agent.chat":
      return p.diagnosis
        ? `Diagnosis: ${p.diagnosis}`
        : p.recommendation
          ? `${p.recommendation}`
          : JSON.stringify(p);
    case "status.report":
      return `Capital: ${p.allocated}/${p.total_capital} allocated`;
    default:
      return JSON.stringify(p).slice(0, 120);
  }
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

interface Props {
  messages: ChainMessage[];
  onClear: () => void;
}

export function MessageFeed({ messages, onClear }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700/60">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            TradeChain Feed
          </h2>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[10px] text-gray-500">live</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-gray-600 tabular-nums">{messages.length}</span>
          <button
            onClick={onClear}
            className="text-[10px] text-gray-500 hover:text-gray-300 px-2 py-0.5 rounded hover:bg-gray-800/50 transition"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5 font-mono text-[11px]">
        {messages.length === 0 && (
          <div className="text-center mt-16">
            <p className="text-xl mb-2">📡</p>
            <p className="text-gray-600 text-xs">
              Waiting for agent activity...
            </p>
            <p className="text-gray-700 text-[10px] mt-1">
              Messages will appear here in real-time via WebSocket
            </p>
          </div>
        )}
        {messages.map((msg) => {
          const style = TYPE_STYLES[msg.type] ?? { color: "text-gray-400", icon: "•", bg: "" };
          return (
            <div
              key={msg.id}
              className={`flex gap-2 py-1 px-2 rounded-md hover:bg-gray-800/40 transition-colors ${style.bg}`}
            >
              <span className="text-gray-600 shrink-0 tabular-nums">{formatTime(msg.timestamp)}</span>
              <span className="shrink-0 w-4 text-center">{style.icon}</span>
              <span className="text-amber-300/80 shrink-0 w-32 truncate font-medium">
                {msg.sender_id}
              </span>
              {msg.target_id && (
                <span className="text-gray-600 shrink-0">
                  <span className="text-gray-700">→</span> {msg.target_id}
                </span>
              )}
              <span className={`truncate ${style.color}`}>
                {formatPayload(msg)}
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
