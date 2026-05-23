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
