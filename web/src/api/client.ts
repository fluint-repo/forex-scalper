const BASE_URL = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(BASE_URL + url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || resp.statusText);
  }
  return resp.json();
}

export const api = {
  getAccount: () => fetchJson<any>('/account'),
  getPositions: () => fetchJson<any[]>('/positions'),
  closePosition: (id: string) =>
    fetchJson<any>(`/positions/${id}/close`, { method: 'POST' }),
  getTrades: (limit = 100) => fetchJson<any[]>(`/trades?limit=${limit}`),
  getCandles: (limit = 250) => fetchJson<any[]>(`/candles?limit=${limit}`),
  getStrategyStatus: () => fetchJson<any>('/strategy/status'),
  startStrategy: (body: any) =>
    fetchJson<any>('/strategy/start', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  stopStrategy: () =>
    fetchJson<any>('/strategy/stop', { method: 'POST' }),
  updateParams: (params: any) =>
    fetchJson<any>('/strategy/params', {
      method: 'PUT',
      body: JSON.stringify({ params }),
    }),
};
