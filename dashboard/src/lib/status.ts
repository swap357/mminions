export const STATUS_COLORS: Record<string, string> = {
  running: '#22c55e',
  done: '#6b7280',
  stopped: '#6b7280',
  finished: '#22c55e',
  failed: '#ef4444',
  timeout: '#eab308',
  active: '#3b82f6',
  unknown: '#6b7280',
};

export function statusColor(s: string): string {
  return STATUS_COLORS[s] ?? '#6b7280';
}

export function statusBgClass(s: string): string {
  const map: Record<string, string> = {
    running: 'bg-status-running',
    done: 'bg-status-done',
    stopped: 'bg-status-stopped',
    finished: 'bg-status-finished',
    failed: 'bg-status-failed',
    timeout: 'bg-status-timeout',
    active: 'bg-status-active',
    unknown: 'bg-status-unknown',
  };
  return map[s] ?? 'bg-status-unknown';
}
