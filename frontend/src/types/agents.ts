export interface AgentStatus {
  agent_id: string;
  role: string;
  status: "idle" | "running" | "paused" | "stopped" | "error";
  metrics: {
    messages_sent: number;
    messages_received: number;
    errors: number;
    cycles: number;
  };
  strategy?: string;
  symbol?: string;
  position?: string;
  realized_pnl?: string;
  total_trades?: number;
}

export interface ChainMessage {
  id: string;
  type: string;
  sender_id: string;
  sender_role: string;
  target_id: string | null;
  priority: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface HealthStatus {
  status: string;
  company: string;
  agents_active: number;
  agents_total: number;
  ws_clients: number;
  ai_available: boolean;
  ai_mode: string;
}

export interface PortfolioSummary {
  total_balance_usdt: string;
  realized_pnl: string;
  unrealized_pnl: string;
  total_pnl: string;
  total_trades: number;
  open_positions: number;
  active_bots: number;
  balances: Record<string, string>;
  strategies: Record<string, {
    count: number;
    pnl: string;
    trades: number;
    positions: number;
  }>;
}

export interface Strategy {
  name: string;
  description: string;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface StoredApiKey {
  id: string;
  exchange: string;
  is_paper: boolean;
  created_at: string;
}

export interface AIProviderInfo {
  id: string;
  display_name: string;
  configured: boolean;
}

export interface AIStatus {
  available: boolean;
  mode: string;
  primary: string;
  fallback_chain: string[];
  valid_modes: string[];
  providers: Record<string, AIProviderInfo>;
}
