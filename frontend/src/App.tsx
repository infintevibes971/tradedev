import { useCallback, useEffect, useState } from "react";
import { AgentNetwork } from "./components/AgentNetwork";
import { Dashboard } from "./components/Dashboard";
import { KeyVault } from "./components/KeyVault";
import { MessageFeed } from "./components/MessageFeed";
import { useWebSocket } from "./hooks/useWebSocket";
import type { AgentStatus, HealthStatus, Strategy, UserProfile } from "./types/agents";

type Tab = "dashboard" | "agents" | "feed" | "settings";

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

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold tracking-tight">
            <span className="text-blue-400">Trade</span>
            <span className="text-amber-400">Dev</span>
          </h1>
          <span className="text-[10px] text-gray-600 border border-gray-700 px-1.5 py-0.5 rounded">
            AI Trading Company
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-[10px] text-gray-500">
              {connected ? "WS Connected" : "WS Disconnected"}
            </span>
          </div>
          {health && (
            <span className="text-[10px] text-gray-500">
              {health.agents_active} agents active
            </span>
          )}
          <button
            onClick={() => setActiveTab("settings")}
            className={`text-xs px-2 py-1 rounded transition ${
              activeTab === "settings"
                ? "bg-blue-900/60 text-blue-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {user ? `⚙ ${user.username}` : "⚙ Settings"}
          </button>
        </div>
      </header>

      {/* Tab bar - mobile */}
      <div className="flex border-b border-gray-800 lg:hidden">
        {(["dashboard", "agents", "feed", "settings"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-xs font-medium uppercase tracking-wider transition ${
              activeTab === tab
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Main layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Dashboard - left panel */}
        <div className={`${
          activeTab === "dashboard" ? "flex" : "hidden"
        } lg:flex flex-col w-full lg:w-1/3 border-r border-gray-800`}>
          <Dashboard
            health={health}
            agents={agents}
            messages={messages}
            strategies={strategies}
            onSpawn={spawnBots}
          />
        </div>

        {/* Message Feed - center panel */}
        <div className={`${
          activeTab === "feed" ? "flex" : "hidden"
        } lg:flex flex-col w-full lg:flex-1 border-r border-gray-800`}>
          <MessageFeed messages={messages} onClear={clearMessages} />
        </div>

        {/* Agent Network - right panel */}
        <div className={`${
          activeTab === "agents" ? "flex" : "hidden"
        } lg:flex flex-col w-full lg:w-1/3`}>
          <AgentNetwork
            agents={agents}
            messages={messages}
            onPause={pauseAgent}
            onResume={resumeAgent}
            onStop={stopAgent}
          />
        </div>

        {/* Settings / Key Vault - overlay panel */}
        {activeTab === "settings" && (
          <div className="absolute inset-0 top-[49px] lg:top-[53px] bg-gray-950/95 backdrop-blur z-10 flex justify-center">
            <div className="w-full max-w-lg">
              <KeyVault user={user} onLogin={handleLogin} onLogout={handleLogout} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
