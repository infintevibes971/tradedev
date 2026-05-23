import { useEffect, useRef } from "react";
import type { ChainMessage } from "../types/agents";

const TYPE_COLORS: Record<string, string> = {
  "trade.executed": "text-green-400",
  "trade.request": "text-blue-400",
  "trade.rejected": "text-red-400",
  "risk.alert": "text-red-500 font-bold",
  "capital.request": "text-yellow-400",
  "capital.response": "text-yellow-300",
  "status.report": "text-gray-400",
  "error.report": "text-red-400",
  "agent.chat": "text-cyan-400",
  "system.command": "text-purple-400",
  "report.weekly": "text-amber-400",
};

const TYPE_ICONS: Record<string, string> = {
  "trade.executed": "⬆",
  "trade.request": "📋",
  "risk.alert": "⚠",
  "capital.request": "💰",
  "capital.response": "✅",
  "error.report": "❌",
  "agent.chat": "💬",
  "system.command": "⚙",
  "status.report": "📊",
  "report.weekly": "📈",
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
  return new Date(ts).toLocaleTimeString();
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
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          TradeChain Live Feed
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{messages.length} msgs</span>
          <button
            onClick={onClear}
            className="text-xs text-gray-500 hover:text-gray-300 transition"
          >
            Clear
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-xs">
        {messages.length === 0 && (
          <p className="text-gray-600 text-center mt-8">
            Waiting for agent activity...
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className="flex gap-2 py-0.5 hover:bg-gray-800/50 px-1 rounded">
            <span className="text-gray-600 shrink-0">{formatTime(msg.timestamp)}</span>
            <span className="shrink-0">{TYPE_ICONS[msg.type] ?? "•"}</span>
            <span className="text-amber-300 shrink-0 w-36 truncate">{msg.sender_id}</span>
            {msg.target_id && (
              <span className="text-gray-500 shrink-0">→ {msg.target_id}</span>
            )}
            <span className={TYPE_COLORS[msg.type] ?? "text-gray-400"}>
              {formatPayload(msg)}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
