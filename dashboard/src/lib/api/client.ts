const API_BASE = '/api/v1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export interface AccountState {
  phone: string;
  state: string;
  previous_state: string;
  state_since: string;
  error_message: string;
  last_event_at: string;
  metrics: {
    messages_1m: number;
    messages_5m: number;
    messages_15m: number;
    reactions_1m: number;
    errors_1h: number;
    active_channels: number;
  };
}

export interface AccountsResponse {
  accounts: AccountState[];
  summary: {
    total: number;
    by_state: Record<string, number>;
  };
}

export interface TimelineEvent {
  timestamp: string;
  event_type: string;
  event_name: string;
  severity: string;
  message: string;
  payload: string;
  entity_type: string;
  entity_id: string;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
  has_more: boolean;
}

export interface PipelineStage {
  status: string;
  throughput: number;
  latency_p50: number;
  latency_p95: number;
}

export interface PipelineHealth {
  status: string;
  stages: Record<string, PipelineStage>;
}

export interface Alert {
  alert_id: string;
  rule_name: string;
  severity: string;
  status: string;
  entity_type: string;
  entity_id: string;
  message: string;
  fired_at: string;
  resolved_at?: string;
  acknowledged_by?: string;
}

export interface AlertsResponse {
  alerts: Alert[];
  firing_count: number;
  total: number;
}

export interface SystemOverview {
  status: string;
  accounts: { total: number; by_state: Record<string, number> };
  pipeline: { status: string };
  alerts: { firing: number; total: number };
  clickhouse: string;
}

export const api = {
  accounts: {
    list: () => request<AccountsResponse>('/accounts'),
    get: (phone: string) => request<AccountState>(`/accounts/${encodeURIComponent(phone)}/state`),
    timeline: (phone: string, limit = 100, offset = 0) =>
      request<TimelineResponse>(`/accounts/${encodeURIComponent(phone)}/timeline?limit=${limit}&offset=${offset}`),
    metrics: (phone: string) =>
      request<any>(`/accounts/${encodeURIComponent(phone)}/metrics`)
  },
  pipeline: {
    health: () => request<PipelineHealth>('/pipeline/health')
  },
  alerts: {
    list: (status?: string) =>
      request<AlertsResponse>(`/alerts${status ? `?status=${status}` : ''}`),
    acknowledge: (id: string) =>
      request<any>(`/alerts/${id}/acknowledge`, { method: 'POST' }),
    rules: {
      list: () => request<{ rules: any[] }>('/alerts/rules'),
      create: (rule: any) =>
        request<any>('/alerts/rules', {
          method: 'POST',
          body: JSON.stringify(rule)
        }),
      update: (name: string, updates: any) =>
        request<any>(`/alerts/rules/${encodeURIComponent(name)}`, {
          method: 'PUT',
          body: JSON.stringify(updates)
        }),
      delete: (name: string) =>
        request<any>(`/alerts/rules/${encodeURIComponent(name)}`, {
          method: 'DELETE'
        })
    }
  },
  anomalies: {
    list: () => request<{ anomalies: any[]; count: number }>('/anomalies')
  },
  system: {
    overview: () => request<SystemOverview>('/system/overview')
  }
};
