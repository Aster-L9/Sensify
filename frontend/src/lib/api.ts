import type {
  AlertItem, AnomalySeries, BaselineAlarms, ConsistencySeries, DashboardSummary, DemoState, EvaluationDetail,
  EvaluationRunOut, GroundTruth, IncidentDetail, IncidentFilters, IncidentSummary, ModelDetail,
  ModelVersion, RunEvent, RunOut, RunState, ScenarioCatalog, ScenarioLaunch, TelemetryPoint, Topology, TrustSeries,
} from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
}

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  setTokens(access: string, refresh: string) {
    this.accessToken = access;
    this.refreshToken = refresh;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
    }
  }

  loadTokens() {
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
      this.refreshToken = localStorage.getItem('refresh_token');
    }
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }

  getAccessToken() {
    if (!this.accessToken && typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
    }
    return this.accessToken;
  }

  async fetch<T = any>(endpoint: string, options: FetchOptions = {}): Promise<T> {
    const { skipAuth, ...fetchOptions } = options;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(fetchOptions.headers as Record<string, string> || {}),
    };

    if (!skipAuth && this.getAccessToken()) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
    });

    if (response.status === 401 && !skipAuth && this.refreshToken) {
      // Try refresh
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        const retryResponse = await fetch(`${API_URL}${endpoint}`, {
          ...fetchOptions,
          headers,
        });
        if (!retryResponse.ok) {
          throw new ApiError(retryResponse.status, await retryResponse.text());
        }
        return retryResponse.json();
      } else {
        this.clearTokens();
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
        throw new ApiError(401, 'Session expired');
      }
    }

    if (!response.ok) {
      let errorMsg = 'Request failed';
      try {
        const errorBody = await response.json();
        errorMsg = describeDetail(errorBody.detail) || errorBody.message || errorMsg;
      } catch {
        errorMsg = await response.text();
      }
      throw new ApiError(response.status, errorMsg);
    }

    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });
      if (response.ok) {
        const data = await response.json();
        this.setTokens(data.access_token, data.refresh_token);
        return true;
      }
    } catch {}
    return false;
  }
}

/** FastAPI validation errors (422) carry a list of problems; show them as one readable sentence. */
function describeDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d: any) => {
      const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : null;
      return field && typeof field === 'string' ? `${field.replace(/_/g, ' ')}: ${d.msg}` : d?.msg;
    }).filter(Boolean);
    return parts.length ? parts.join('; ') : null;
  }
  return null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

export const api = new ApiClient();

// ── Convenience methods ──────────────────────────────────────────────────────
export async function login(email: string, password: string) {
  const data = await api.fetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
  api.setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function register(username: string, email: string, password: string) {
  const data = await api.fetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
    skipAuth: true,
  });
  api.setTokens(data.access_token, data.refresh_token);
  return data;
}

export function logout() {
  api.clearTokens();
  if (typeof window !== 'undefined') {
    window.location.href = '/';
  }
}

export async function getMe() {
  return api.fetch('/auth/me');
}

export async function changePassword(current_password: string, new_password: string) {
  return api.fetch('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password, new_password }),
  });
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return api.fetch('/dashboard/summary');
}

export async function getTopology(): Promise<Topology> {
  return api.fetch('/topology');
}

export const RUNS_PAGE_LIMIT = 200; // the API's maximum page size

export async function getRuns(status?: string): Promise<RunOut[]> {
  const params = new URLSearchParams({ limit: String(RUNS_PAGE_LIMIT) });
  if (status) params.set('status', status);
  return api.fetch(`/runs?${params}`);
}

export async function getRun(id: number): Promise<RunOut> {
  return api.fetch(`/runs/${id}`);
}

export async function getRunState(id: number, at?: number): Promise<RunState> {
  const params = at === undefined ? '' : `?at=${at}`;
  return api.fetch(`/runs/${id}/state${params}`);
}

/** Launch a normal-operation run (quick launch). */
export async function createRun(data: { name?: string; description?: string; seed?: number }): Promise<RunOut> {
  return api.fetch('/runs', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Shared playback control (administrators): every viewer sees the paused or rewound moment. */
export async function pauseRun(id: number): Promise<RunOut> {
  return api.fetch(`/runs/${id}/pause`, { method: 'POST' });
}

export async function resumeRun(id: number): Promise<RunOut> {
  return api.fetch(`/runs/${id}/resume`, { method: 'POST' });
}

export async function resetRun(id: number): Promise<RunOut> {
  return api.fetch(`/runs/${id}/reset`, { method: 'POST' });
}

export async function getTelemetry(
  runId: number,
  opts: { segmentId?: number; fromTick?: number; toTick?: number; limit?: number } = {},
): Promise<TelemetryPoint[]> {
  const params = new URLSearchParams({ run_id: String(runId) });
  if (opts.segmentId !== undefined) params.set('segment_id', String(opts.segmentId));
  if (opts.fromTick !== undefined) params.set('from_tick', String(opts.fromTick));
  if (opts.toTick !== undefined) params.set('to_tick', String(opts.toTick));
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  return api.fetch(`/telemetry?${params}`);
}

// ── Sprint 2: scenarios, analysis, alerts, models ────────────────────────────
export async function getScenarios(): Promise<ScenarioCatalog> {
  return api.fetch('/scenarios');
}

export async function launchScenario(body: ScenarioLaunch): Promise<RunOut> {
  return api.fetch('/scenarios', { method: 'POST', body: JSON.stringify(body) });
}

export async function getRunEvents(runId: number, opts: { category?: string; segmentId?: number } = {}): Promise<RunEvent[]> {
  const params = new URLSearchParams();
  if (opts.category) params.set('category', opts.category);
  if (opts.segmentId !== undefined) params.set('segment_id', String(opts.segmentId));
  const qs = params.toString();
  return api.fetch(`/runs/${runId}/events${qs ? `?${qs}` : ''}`);
}

export async function getAnomalies(runId: number): Promise<AnomalySeries> {
  return api.fetch(`/runs/${runId}/anomalies`);
}

export async function getTrust(runId: number): Promise<TrustSeries> {
  return api.fetch(`/runs/${runId}/telemetry-trust`);
}

export async function getConsistency(runId: number): Promise<ConsistencySeries> {
  return api.fetch(`/runs/${runId}/consistency`);
}

export async function getBaselineAlarms(runId: number): Promise<BaselineAlarms> {
  return api.fetch(`/runs/${runId}/baseline-alarms`);
}

export async function rescoreRun(runId: number): Promise<{ run_id: number; model_version: number; alerts: number }> {
  return api.fetch(`/runs/${runId}/score`, { method: 'POST' });
}

export async function getGroundTruth(runId: number): Promise<GroundTruth> {
  return api.fetch(`/runs/${runId}/ground-truth`);
}

export async function getAlerts(filters: {
  runId?: number;
  segmentId?: number;
  severity?: string;
  kind?: string;
  fromTick?: number;
  toTick?: number;
  limit?: number;
} = {}): Promise<AlertItem[]> {
  const params = new URLSearchParams();
  if (filters.fromTick !== undefined) params.set('from_tick', String(filters.fromTick));
  if (filters.toTick !== undefined) params.set('to_tick', String(filters.toTick));
  if (filters.runId !== undefined) params.set('run_id', String(filters.runId));
  if (filters.segmentId !== undefined) params.set('segment_id', String(filters.segmentId));
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.kind) params.set('kind', filters.kind);
  params.set('limit', String(filters.limit ?? 200));
  return api.fetch(`/alerts?${params}`);
}

export async function getModels(): Promise<ModelVersion[]> {
  return api.fetch('/models');
}

export async function getModel(id: number): Promise<ModelDetail> {
  return api.fetch(`/models/${id}`);
}

export async function trainModel(body: { n_estimators: number; max_samples: number; alpha: number }): Promise<ModelVersion> {
  return api.fetch('/models/train', { method: 'POST', body: JSON.stringify(body) });
}

export async function activateModel(id: number): Promise<ModelVersion> {
  return api.fetch(`/models/${id}/activate`, { method: 'POST' });
}

export async function getActivity(limit: number = 20) {
  return api.fetch(`/activity?limit=${limit}`);
}

export async function getUsers() {
  return api.fetch('/users');
}

export async function createUser(data: { username: string; email: string; password: string; role: 'analyst' | 'admin' }) {
  return api.fetch('/users/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateUser(id: number, data: { role?: string; is_active?: boolean }) {
  return api.fetch(`/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteUser(id: number) {
  return api.fetch(`/users/${id}`, {
    method: 'DELETE',
  });
}

// ── Sprint 3: incidents, evaluation, demo, reports ───────────────────────────
export async function getIncidents(filters: IncidentFilters = {}): Promise<IncidentSummary[]> {
  const params = new URLSearchParams();
  if (filters.runId !== undefined) params.set('run_id', String(filters.runId));
  if (filters.classification) params.set('classification', filters.classification);
  if (filters.status) params.set('status', filters.status);
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.segment) params.set('segment', filters.segment);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.order) params.set('order', filters.order);
  params.set('limit', String(filters.limit ?? 200));
  return api.fetch(`/incidents?${params}`);
}

export async function getRunIncidents(runId: number): Promise<IncidentSummary[]> {
  return api.fetch(`/runs/${runId}/incidents`);
}

export async function getIncident(key: string): Promise<IncidentDetail> {
  return api.fetch(`/incidents/${encodeURIComponent(key)}`);
}

export async function setIncidentStatus(
  key: string, status: 'investigating' | 'resolved', note?: string,
): Promise<IncidentDetail> {
  return api.fetch(`/incidents/${encodeURIComponent(key)}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, note: note ?? null }),
  });
}

export async function getEvaluations(): Promise<EvaluationRunOut[]> {
  return api.fetch('/evaluation');
}

export async function getLatestEvaluation(): Promise<EvaluationDetail> {
  return api.fetch('/evaluation/latest');
}

export async function getEvaluation(id: number): Promise<EvaluationDetail> {
  return api.fetch(`/evaluation/${id}`);
}

export async function runEvaluation(): Promise<EvaluationRunOut> {
  return api.fetch('/evaluation', { method: 'POST' });
}

export async function startDemo(): Promise<DemoState> {
  return api.fetch('/demo', { method: 'POST' });
}

export async function getDemo(): Promise<DemoState> {
  return api.fetch('/demo');
}

export function reportUrl(kind: 'incident' | 'evaluation', id: string | number, format: 'pdf' | 'csv'): string {
  return `${API_URL}/reports/${kind}/${encodeURIComponent(String(id))}?format=${format}`;
}

/** Fetch a report with the bearer token (a plain link can't send it) and save it as a file. */
export async function downloadReport(
  kind: 'incident' | 'evaluation', id: string | number, format: 'pdf' | 'csv',
): Promise<void> {
  const token = api.getAccessToken();
  const response = await fetch(reportUrl(kind, id, format), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    let msg = 'Report download failed';
    try {
      const body = await response.json();
      msg = body.detail || body.message || msg;
    } catch {}
    throw new ApiError(response.status, msg);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sensify-${kind}-${id}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
