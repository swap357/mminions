import type {
  HealthResponse,
  RunsResponse,
  RunStatus,
  LaunchPayload,
  LaunchResponse,
  StopResponse,
  SendResponse,
} from './types';

const BASE = '';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json() as Promise<T>;
}

export const fetchHealth = () => request<HealthResponse>('/health');

export const fetchRuns = () => request<RunsResponse>('/api/runs');

export const fetchStatus = (runId: string, lines = 120) =>
  request<RunStatus>(`/api/runs/${runId}/status?lines=${lines}`);

export const postLaunch = (payload: LaunchPayload) =>
  request<LaunchResponse>('/api/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const postStop = (runId: string) =>
  request<StopResponse>(`/api/runs/${runId}/stop`, { method: 'POST' });

export const postSend = (runId: string, worker: string, text: string) =>
  request<SendResponse>(`/api/runs/${runId}/send`, {
    method: 'POST',
    body: JSON.stringify({ worker, text }),
  });
