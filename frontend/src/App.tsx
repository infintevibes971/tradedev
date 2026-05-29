import { useCallback, useEffect, useState } from "react";
import { AgentNetwork } from "./components/AgentNetwork";
import { Dashboard } from "./components/Dashboard";
import { KeyVault } from "./components/KeyVault";
import { MessageFeed } from "./components/MessageFeed";
import { useWebSocket } from "./hooks/useWebSocket";
import type { AgentStatus, HealthStatus, Strategy, UserProfile } from "./types/agents";

type Tab = "dashboard" | "agents" | "feed" | "settings";

const TAB_META: Record<Tab, { label: string; icon: string }> = {
  dashboard: { label: "Dashboard", icon: "grid" },
  agents: { label: "Agents", icon: "users" },
  feed: { label: "Feed", icon: "activity" },
  settings: { label: "Settings", icon: "settings" },
};

function TabIcon({ name, className }: { name: string; className?: string }) {
  const cn = className ?? "w-4 h-4";
  switch (name) {
    case "grid":
      return (
        <svg className={cn} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
      );
    case "users":
      return (
        <svg className={cn} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
        </svg>
      );
    case "activity":
      return (
        <svg className={cn} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
        </svg>
      );
    case "settings":
      return (
        <svg className={cn} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      );
    default:
      return null;
  }
}

function App() {
  const { messages, connected, clearMessages } = useWebSocket();
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("tradedev_user");
    return saved ? JSON.parse(saved) : null;
  });

  const handleLogin = useCallback((u: UserProfile) => {
    setUser(u);
    localStorage.setItem("tradedev_user", JSON.stringify(u));
    // Auto-connect stored exchange keys on login
    fetch("/api/portfolio/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: u.id }),
    }).catch(() => {});
  }, []);

  const handleLogout = useCallback(() => {
    setUser(null);
    localStorage.removeItem("tradedev_user");
  }, []);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch("/agents");
      if (res.ok) setAgents(await res.json());
    } catch { /* server not up yet */ }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch("/health");
      if (res.ok) setHealth(await res.json());
    } catch { /* server not up yet */ }
  }, []);

  const fetchStrategies = useCallback(async () => {
    try {
      const res = await fetch("/api/agents/strategies");
      if (res.ok) setStrategies(await res.json());
    } catch { /* server not up yet */ }
  }, []);

  // Auto-connect exchanges when app loads with a saved user session
  useEffect(() => {
    if (user) {
      fetch("/api/portfolio/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id }),
      }).catch(() => {});
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchAgents();
    fetchHealth();
    fetchStrategies();
    const interval = setInterval(() => {
      fetchAgents();
      fetchHealth();
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchAgents, fetchHealth, fetchStrategies]);

  const spawnBots = useCallback(async (strategy: string, symbol: string, count: number) => {
    await fetch("/api/agents/spawn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy, symbol, count }),
    });
    fetchAgents();
    fetchHealth();
  }, [fetchAgents, fetchHealth]);

  const pauseAgent = useCallback(async (id: string) => {
    await fetch(`/api/agents/${id}/pause`, { method: "POST" });
    fetchAgents();
  }, [fetchAgents]);

  const resumeAgent = useCallback(async (id: string) => {
    await fetch(`/api/agents/${id}/resume`, { method: "POST" });
    fetchAgents();
  }, [fetchAgents]);

  const stopAgent = useCallback(async (id: string) => {
    await fetch(`/api/agents/${id}`, { method: "DELETE" });
    fetchAgents();
    fetchHealth();
  }, [fetchAgents, fetchHealth]);

  const traders = agents.filter((a) => a.role.startsWith("trader:"));
  const totalPnl = traders.reduce((s, a) => s + Number(a.realized_pnl ?? 0), 0);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-5 py-2.5 border-b border-gray-800/80 bg-gray-900/90 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-amber-500 flex items-center justify-center">
              <span className="text-[11px] font-black text-white">TD</span>
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight leading-none">
                <span className="text-blue-400">Trade</span>
                <span className="text-amber-400">Dev</span>
              </h1>
              <p className="text-[8px] text-gray-600 tracking-wider uppercase leading-none mt-0.5">
                AI Trading Company
              </p>
            </div>
          </div>
        </div>

        {/* Header right: live stats */}
        <div className="flex items-center gap-4">
          {/* P&L badge in header */}
          {traders.length > 0 && (
            <div className={`text-xs font-semibold px-2 py-1 rounded-md ${
              totalPnl >= 0
                ? "bg-green-900/30 text-green-400"
                : "bg-red-900/30 text-red-400"
            }`}>
              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)}
            </div>
          )}

          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-[10px] text-gray-500">
              {connected ? "Live" : "Offline"}
            </span>
          </div>

          {health && (
            <span className="text-[10px] text-gray-500">
              {health.agents_active} bots
            </span>
          )}

          <button
            onClick={() => setActiveTab("settings")}
            className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition ${
              activeTab === "settings"
                ? "bg-gray-800 text-gray-200"
                : "text-gray-500 hover:text-gray-300 hover:bg-gray-800/50"
            }`}
          >
            <TabIcon name="settings" className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">
              {user ? user.username : "Settings"}
            </span>
          </button>
        </div>
      </header>

      {/* ── Tab bar (mobile) ────────────────────────────────────── */}
      <div className="flex border-b border-gray-800/60 lg:hidden bg-gray-900/50">
        {(["dashboard", "agents", "feed", "settings"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 flex flex-col items-center gap-0.5 py-2 transition ${
              activeTab === tab
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <TabIcon name={TAB_META[tab].icon} className="w-4 h-4" />
            <span className="text-[9px] font-medium uppercase tracking-wider">
              {TAB_META[tab].label}
            </span>
          </button>
        ))}
      </div>

      {/* ── Main layout ─────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Dashboard — left panel */}
        <div className={`${
          activeTab === "dashboard" ? "flex" : "hidden"
        } lg:flex flex-col w-full lg:w-[340px] xl:w-[380px] border-r border-gray-800/60`}>
          <Dashboard
            health={health}
            agents={agents}
            messages={messages}
            strategies={strategies}
            onSpawn={spawnBots}
            onGoToSettings={() => setActiveTab("settings")}
          />
        </div>

        {/* Message Feed — center panel */}
        <div className={`${
          activeTab === "feed" ? "flex" : "hidden"
        } lg:flex flex-col w-full lg:flex-1 border-r border-gray-800/60`}>
          <MessageFeed messages={messages} onClear={clearMessages} />
        </div>

        {/* Agent Network — right panel */}
        <div className={`${
          activeTab === "agents" ? "flex" : "hidden"
        } lg:flex flex-col w-full lg:w-[340px] xl:w-[380px]`}>
          <AgentNetwork
            agents={agents}
            messages={messages}
            onPause={pauseAgent}
            onResume={resumeAgent}
            onStop={stopAgent}
          />
        </div>

        {/* Settings overlay */}
        {activeTab === "settings" && (
          <div className="absolute inset-0 bg-gray-950/95 backdrop-blur-sm z-10 flex flex-col overflow-y-auto">
            {/* Back button bar */}
            <div className="sticky top-0 z-20 bg-gray-900/90 backdrop-blur-xl border-b border-gray-800/60 px-4 py-2.5 flex items-center justify-between">
              <button
                onClick={() => setActiveTab("dashboard")}
                className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-100 transition"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                </svg>
                <span>Back to Dashboard</span>
              </button>
              <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                Settings
              </h2>
            </div>
            <div className="flex-1 flex justify-center">
              <div className="w-full max-w-lg py-4">
                <KeyVault user={user} onLogin={handleLogin} onLogout={handleLogout} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
