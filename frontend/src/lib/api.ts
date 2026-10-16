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
        errorMsg = errorBody.detail || errorBody.message || errorMsg;
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

export async function getDashboardSummary() {
  return api.fetch('/dashboard/summary');
}

export async function getTopology() {
  return api.fetch('/topology');
}

export async function getRuns(status?: string) {
  const params = status ? `?status=${status}` : '';
  return api.fetch(`/runs${params}`);
}

export async function getRun(id: number) {
  return api.fetch(`/runs/${id}`);
}

export async function getRunState(id: number) {
  return api.fetch(`/runs/${id}/state`);
}

export async function createRun(data: { name: string; description?: string; seed?: number }) {
  return api.fetch('/runs', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getTelemetry(runId: number, segmentId?: number, limit?: number) {
  const params = new URLSearchParams({ run_id: String(runId) });
  if (segmentId) params.set('segment_id', String(segmentId));
  if (limit) params.set('limit', String(limit));
  return api.fetch(`/telemetry?${params}`);
}

export async function getActivity(limit: number = 20) {
  return api.fetch(`/activity?limit=${limit}`);
}

export async function getUsers() {
  return api.fetch('/users');
}

export async function createUser(data: { username: string; email: string; password: string; role: string }) {
  return api.fetch('/users', {
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
