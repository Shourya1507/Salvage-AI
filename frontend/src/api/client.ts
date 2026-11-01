import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
    'x-admin-token': 'admin_secret_token_123',
  },
});

export interface DashboardData {
  total_mrr_at_risk: number;
  total_recovered_mrr: number;
  mrr_at_risk_by_type: Record<string, number>;
  open_cases: number;
  case_counts_by_status: Record<string, number>;
  case_counts_by_type: Record<string, number>;
  priority_cases: Array<{
    id: string;
    type: string;
    severity: number;
    mrr_at_risk: number;
    status: string;
    opened_at: string;
  }>;
}

export interface Proposal {
  id: string;
  case_id: string;
  action_type: string;
  diagnosis: string;
  reasoning: string;
  customer_message: string;
  confidence: number;
  params: Record<string, any>;
  status: 'pending' | 'approved' | 'dismissed' | 'executed' | 'failed';
  created_at: string;
  decided_at?: string | null;
  decided_by?: string | null;
  model: string;
}

export interface CaseItem {
  id: string;
  subscription_id: string;
  type: string;
  severity: number;
  mrr_at_risk: number;
  status: 'open' | 'proposed' | 'resolved' | 'dismissed' | 'needs_review';
  evidence?: Record<string, any>;
  opened_at: string;
  updated_at?: string;
  resolved_at?: string | null;
  subscription?: {
    id: string;
    paypal_subscription_id: string;
    status: string;
    source: 'real' | 'simulated';
    start_time: string;
  };
  subscriber?: {
    id: string;
    name: string;
    email: string;
    source: 'real' | 'simulated';
  };
  plan?: {
    id: string;
    name: string;
    price: number;
    currency: string;
    interval: string;
  };
  proposals?: Proposal[];
}

export interface ActionLogItem {
  id: string;
  proposal_id: string;
  case_id: string;
  action_type: string;
  executed_at: string;
  executed_by: string;
  success: boolean;
  paypal_response_code?: number | null;
  recovered_mrr?: number | null;
  error_message?: string | null;
}

export interface HealthState {
  status: 'healthy' | 'degraded';
  db: string;
  paypal: string;
  llm: string;
  demo_mode: boolean;
  executor_enabled: boolean;
  paypal_env: string;
}

export interface DemoState {
  is_demo_mode: boolean;
  subscriber_count: number;
  subscription_count: number;
  case_count: number;
  action_count: number;
}

// API functions
export const getDashboard = async (): Promise<DashboardData> => {
  const res = await api.get('/api/dashboard');
  return res.data;
};

export const getCases = async (params?: {
  status?: string;
  case_type?: string;
  limit?: number;
}): Promise<CaseItem[]> => {
  const res = await api.get('/api/cases', { params });
  return res.data;
};

export const getCaseDetail = async (caseId: string): Promise<CaseItem> => {
  const res = await api.get(`/api/cases/${caseId}`);
  return res.data;
};

export const runAgentForCase = async (caseId: string): Promise<any> => {
  const res = await api.post(`/api/cases/${caseId}/run-agent`);
  return res.data;
};

export const approveProposal = async (
  proposalId: string,
  editedParams?: Record<string, any>
): Promise<any> => {
  const res = await api.post(`/api/proposals/${proposalId}/approve`, {
    edited_params: editedParams,
    decided_by: 'merchant',
  });
  return res.data;
};

export const dismissProposal = async (
  proposalId: string,
  reason: string = 'Dismissed by merchant'
): Promise<any> => {
  const res = await api.post(`/api/proposals/${proposalId}/dismiss`, {
    reason,
    decided_by: 'merchant',
  });
  return res.data;
};

export const getActionLogs = async (limit: number = 50): Promise<ActionLogItem[]> => {
  const res = await api.get('/api/actions', { params: { limit } });
  return res.data;
};

export const getHealth = async (): Promise<HealthState> => {
  const res = await api.get('/healthz');
  return res.data;
};

export const getDemoState = async (): Promise<DemoState> => {
  const res = await api.get('/api/demo/state');
  return res.data;
};

export const seedDemoData = async (subscribers: number = 25): Promise<any> => {
  const res = await api.post('/api/demo/seed', { subscribers, active_ratio: 0.8 });
  return res.data;
};

export const injectScenario = async (
  scenario: 'failed_payment' | 'duplicate_charge' | 'price_change' | 'stalled_suspension'
): Promise<any> => {
  const res = await api.post('/api/demo/inject', { scenario });
  return res.data;
};

export const resetDemoData = async (): Promise<any> => {
  const res = await api.post('/api/demo/reset');
  return res.data;
};

export const runSync = async (): Promise<any> => {
  const res = await api.post('/api/sync/run');
  return res.data;
};

export default api;
