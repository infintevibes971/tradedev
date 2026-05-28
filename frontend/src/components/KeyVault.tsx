import { useCallback, useEffect, useState } from "react";
import type { AIStatus, StoredApiKey, UserProfile } from "../types/agents";

const EXCHANGES = [
  { value: "binance", label: "Binance" },
  { value: "okx", label: "OKX" },
  { value: "alpaca", label: "Alpaca" },
  { value: "coinbase", label: "Coinbase" },
  { value: "kraken", label: "Kraken" },
  { value: "bybit", label: "Bybit" },
];

interface Props {
  user: UserProfile | null;
  onLogin: (user: UserProfile) => void;
  onLogout: () => void;
}

function AuthForm({ onLogin }: { onLogin: (user: UserProfile) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint = mode === "login" ? "/api/users/login" : "/api/users/register";
    const body =
      mode === "login"
        ? { username, password }
        : { username, email, password };

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Request failed");
      onLogin(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-6 max-w-sm mx-auto">
      <div className="flex gap-2 mb-4">
        {(["login", "register"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setError(""); }}
            className={`flex-1 py-1.5 text-xs font-medium uppercase tracking-wider rounded transition ${
              mode === m
                ? "bg-blue-900/60 text-blue-400 border border-blue-700/50"
                : "text-gray-500 hover:text-gray-300 border border-transparent"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-3">
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />
        {mode === "register" && (
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
          />
        )}
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />
        {error && <p className="text-xs text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded transition"
        >
          {loading ? "..." : mode === "login" ? "Sign In" : "Create Account"}
        </button>
      </form>
    </div>
  );
}

const PASSPHRASE_EXCHANGES = ["okx"];

function AddKeyForm({ userId, onAdded }: { userId: string; onAdded: () => void }) {
  const [exchange, setExchange] = useState(EXCHANGES[0].value);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [isPaper, setIsPaper] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const needsPassphrase = PASSPHRASE_EXCHANGES.includes(exchange);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        exchange,
        api_key: apiKey,
        api_secret: apiSecret,
        is_paper: isPaper,
      };
      if (needsPassphrase) payload.passphrase = passphrase;

      const res = await fetch(`/api/users/${userId}/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed to save key");
      setApiKey("");
      setApiSecret("");
      setPassphrase("");
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex gap-2">
        <select
          value={exchange}
          onChange={(e) => setExchange(e.target.value)}
          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
        >
          {EXCHANGES.map((ex) => (
            <option key={ex.value} value={ex.value}>{ex.label}</option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-gray-400 bg-gray-800 border border-gray-700 rounded px-3 cursor-pointer">
          <input
            type="checkbox"
            checked={isPaper}
            onChange={(e) => setIsPaper(e.target.checked)}
            className="accent-blue-500"
          />
          Paper
        </label>
      </div>
      <input
        type="password"
        placeholder="API Key"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        required
        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
      />
      <input
        type="password"
        placeholder="API Secret"
        value={apiSecret}
        onChange={(e) => setApiSecret(e.target.value)}
        required
        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
      />
      {needsPassphrase && (
        <input
          type="password"
          placeholder="Passphrase (required for OKX)"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-amber-700/50 rounded text-sm text-gray-200 placeholder-gray-500 focus:border-amber-500 focus:outline-none"
        />
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 text-sm font-medium bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded transition"
      >
        {loading ? "Encrypting..." : "Save Key (AES Encrypted)"}
      </button>
    </form>
  );
}

const MODE_INFO: Record<string, { label: string; desc: string }> = {
  single: { label: "Single", desc: "Primary provider + fallback chain" },
  consensus: { label: "Consensus", desc: "Two providers must agree" },
  disabled: { label: "Disabled", desc: "No AI — technicals only" },
};

function AIProviderPanel() {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [switching, setSwitching] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/ai/status");
      if (res.ok) setStatus(await res.json());
    } catch { /* */ }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const switchMode = async (mode: string) => {
    setSwitching(true);
    try {
      const res = await fetch("/api/ai/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (res.ok) await fetchStatus();
    } finally {
      setSwitching(false);
    }
  };

  const switchPrimary = async (provider: string) => {
    setSwitching(true);
    try {
      const res = await fetch("/api/ai/primary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider }),
      });
      if (res.ok) await fetchStatus();
    } finally {
      setSwitching(false);
    }
  };

  if (!status) return null;

  const providers = Object.values(status.providers);
  const configuredCount = providers.filter((p) => p.configured).length;

  return (
    <div className="bg-gray-900/50 border border-purple-700/30 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-purple-400 uppercase tracking-wider">
          AI Providers
        </h3>
        <span className={`text-[10px] px-2 py-0.5 rounded ${
          status.available
            ? "bg-green-900/40 text-green-400"
            : "bg-gray-800 text-gray-500"
        }`}>
          {status.available ? `${configuredCount} active` : "offline"}
        </span>
      </div>

      {/* Provider list */}
      <div className="space-y-1.5 mb-3">
        {providers.map((p) => (
          <div
            key={p.id}
            className={`flex items-center justify-between px-3 py-2 rounded-lg transition cursor-pointer ${
              p.id === status.primary
                ? "bg-purple-900/30 border border-purple-700/40"
                : "bg-gray-800/50 border border-transparent hover:border-gray-700/50"
            }`}
            onClick={() => p.configured && switchPrimary(p.id)}
          >
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                p.configured ? "bg-green-500" : "bg-gray-600"
              }`} />
              <span className="text-xs text-gray-200">{p.display_name}</span>
            </div>
            <div className="flex items-center gap-2">
              {p.id === status.primary && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-900/50 text-purple-300">
                  primary
                </span>
              )}
              {!p.configured && (
                <span className="text-[9px] text-gray-600">no key</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Mode selector */}
      <div className="border-t border-gray-700/50 pt-3">
        <p className="text-[10px] text-gray-500 mb-2">AI Mode</p>
        <div className="flex gap-1.5">
          {status.valid_modes.map((m) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              disabled={switching}
              className={`flex-1 py-1.5 text-[10px] font-medium uppercase tracking-wider rounded transition ${
                m === status.mode
                  ? "bg-purple-900/60 text-purple-300 border border-purple-700/50"
                  : "text-gray-500 hover:text-gray-300 border border-gray-700/30 hover:border-gray-600"
              }`}
              title={MODE_INFO[m]?.desc}
            >
              {MODE_INFO[m]?.label ?? m}
            </button>
          ))}
        </div>
        <p className="text-[10px] text-gray-600 mt-1.5">
          {MODE_INFO[status.mode]?.desc ?? status.mode}
        </p>
      </div>

      {/* Env keys hint */}
      <div className="border-t border-gray-700/50 pt-3 mt-3">
        <p className="text-[10px] text-gray-500 mb-1">
          Set provider API keys in the server <code className="text-purple-400 bg-gray-800 px-1 rounded">.env</code> file:
        </p>
        <code className="block text-[9px] text-gray-500 bg-gray-800 rounded p-2 font-mono leading-relaxed">
          ANTHROPIC_API_KEY=sk-ant-...<br/>
          OPENAI_API_KEY=sk-...<br/>
          GEMINI_API_KEY=AI...
        </code>
      </div>
    </div>
  );
}

export function KeyVault({ user, onLogin, onLogout }: Props) {
  const [keys, setKeys] = useState<StoredApiKey[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/users/${user.id}/keys`);
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys);
      }
    } catch { /* */ }
  }, [user]);

  const connectExchanges = useCallback(async () => {
    if (!user) return;
    setConnecting(true);
    setConnectionStatus(null);
    try {
      const res = await fetch("/api/portfolio/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id }),
      });
      const data = await res.json();
      if (res.ok) {
        const active = data.active?.active_exchange ?? "paper";
        const isLive = data.active?.is_live ?? false;
        setConnectionStatus(
          isLive
            ? `Connected to ${active.toUpperCase()}`
            : "Using paper trading"
        );
      } else {
        setConnectionStatus(`Error: ${data.detail ?? "connection failed"}`);
      }
    } catch (err) {
      setConnectionStatus("Connection failed — check server logs");
    } finally {
      setConnecting(false);
    }
  }, [user]);

  const deleteKey = async (keyId: string) => {
    if (!user) return;
    setDeleting(keyId);
    try {
      await fetch(`/api/users/${user.id}/keys/${keyId}`, { method: "DELETE" });
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
    } finally {
      setDeleting(null);
    }
  };

  useState(() => { fetchKeys(); });

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            Settings & Key Vault
          </h2>
          {user && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500">{user.username}</span>
              <button
                onClick={onLogout}
                className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400 hover:text-red-400 transition"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!user ? (
          <>
            <div className="text-center mb-4">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-900/30 border border-amber-700/40 rounded-lg">
                <span className="text-amber-400 text-lg">&#9919;</span>
                <p className="text-xs text-amber-300">
                  Sign in to connect exchange API keys for live trading
                </p>
              </div>
            </div>
            <AuthForm onLogin={onLogin} />
            <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                How It Works
              </h3>
              <ul className="space-y-2 text-xs text-gray-500">
                <li className="flex gap-2">
                  <span className="text-green-500 shrink-0">1.</span>
                  Create an account or sign in
                </li>
                <li className="flex gap-2">
                  <span className="text-green-500 shrink-0">2.</span>
                  Add your exchange API keys (Binance, Alpaca, etc.)
                </li>
                <li className="flex gap-2">
                  <span className="text-green-500 shrink-0">3.</span>
                  Keys are encrypted with AES-128 before storage
                </li>
                <li className="flex gap-2">
                  <span className="text-green-500 shrink-0">4.</span>
                  Toggle between paper and live trading per key
                </li>
              </ul>
            </div>
            {/* AI Provider panel (visible without login) */}
            <AIProviderPanel />
          </>
        ) : (
          <>
            {/* User profile */}
            <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-900/60 border border-blue-700/50 flex items-center justify-center text-blue-400 font-bold text-lg">
                  {user.username[0].toUpperCase()}
                </div>
                <div>
                  <p className="text-sm text-gray-200 font-medium">{user.username}</p>
                  <p className="text-[10px] text-gray-500">{user.email}</p>
                </div>
              </div>
            </div>

            {/* Connected keys */}
            <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Connected Exchanges ({keys.length})
                </h3>
                <button
                  onClick={() => setShowAddForm(!showAddForm)}
                  className="text-[10px] px-2 py-0.5 rounded bg-green-900/50 text-green-400 hover:bg-green-900 transition"
                >
                  {showAddForm ? "Cancel" : "+ Add Key"}
                </button>
              </div>

              {showAddForm && (
                <div className="mb-4 pb-4 border-b border-gray-700/50">
                  <AddKeyForm
                    userId={user.id}
                    onAdded={() => { fetchKeys(); setShowAddForm(false); }}
                  />
                </div>
              )}

              {keys.length === 0 ? (
                <div className="text-center py-6">
                  <p className="text-2xl mb-2">&#128274;</p>
                  <p className="text-xs text-gray-500">
                    No exchange keys connected yet
                  </p>
                  <p className="text-[10px] text-gray-600 mt-1">
                    The platform runs in paper trading mode by default
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {keys.map((k) => (
                    <div
                      key={k.id}
                      className="flex items-center justify-between bg-gray-800/50 rounded-lg px-3 py-2"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-gray-700/50 flex items-center justify-center text-xs font-bold text-gray-300 uppercase">
                          {k.exchange.slice(0, 2)}
                        </div>
                        <div>
                          <p className="text-sm text-gray-200 font-medium capitalize">
                            {k.exchange}
                          </p>
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                              k.is_paper
                                ? "bg-amber-900/40 text-amber-400"
                                : "bg-green-900/40 text-green-400"
                            }`}>
                              {k.is_paper ? "Paper" : "Live"}
                            </span>
                            <span className="text-[10px] text-gray-600">
                              Added {new Date(k.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => deleteKey(k.id)}
                        disabled={deleting === k.id}
                        className="text-[10px] px-2 py-1 rounded text-gray-500 hover:text-red-400 hover:bg-red-900/20 transition"
                      >
                        {deleting === k.id ? "..." : "Remove"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Connect exchanges — activates stored keys */}
            {keys.length > 0 && (
              <div className="bg-gray-900/50 border border-green-700/30 rounded-lg p-4">
                <h3 className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2">
                  Go Live
                </h3>
                <p className="text-[11px] text-gray-500 mb-3">
                  Connect your stored exchange keys to see real balances and enable live trading.
                </p>
                <button
                  onClick={connectExchanges}
                  disabled={connecting}
                  className="w-full py-2.5 text-sm font-semibold bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg transition"
                >
                  {connecting ? "Connecting..." : "Connect Exchanges"}
                </button>
                {connectionStatus && (
                  <p className={`text-[11px] mt-2 text-center ${
                    connectionStatus.startsWith("Error") || connectionStatus.startsWith("Connection failed")
                      ? "text-red-400"
                      : "text-green-400"
                  }`}>
                    {connectionStatus}
                  </p>
                )}
              </div>
            )}

            {/* Security info */}
            <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Security
              </h3>
              <ul className="space-y-1.5 text-[11px] text-gray-500">
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-0.5 shrink-0">&#10003;</span>
                  Keys encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-0.5 shrink-0">&#10003;</span>
                  Plaintext keys are never stored or logged
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-0.5 shrink-0">&#10003;</span>
                  Paper trading mode is the default — live requires opt-in
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-0.5 shrink-0">&#10003;</span>
                  Password hashed with bcrypt (cost factor 12)
                </li>
              </ul>
            </div>

            {/* AI Provider management */}
            <AIProviderPanel />
          </>
        )}
      </div>
    </div>
  );
}
