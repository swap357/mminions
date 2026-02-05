export interface HealthResponse {
  ok: boolean;
}

export interface RunsResponse {
  runs: string[];
  count: number;
}

export interface WorkerStatus {
  worker_id: string;
  role: string;
  status: string;
  session_name: string;
  session_exists: boolean;
  worktree_path: string;
  output_path: string;
  script_path: string;
  pane_tail: string;
}

export interface ManagerStatus {
  session_name: string;
  session_exists: boolean;
  pane_tail: string;
  issue_url: string;
}

export interface StatusSummary {
  total: number;
  active: number;
  finished: number;
  failed: number;
  timeout: number;
  unknown: number;
}

export interface RunStatus {
  run_id: string;
  run_state: string;
  manager: ManagerStatus;
  workers: WorkerStatus[];
  summary: StatusSummary;
  decision: Record<string, unknown>;
  run_done: Record<string, unknown>;
  error?: string;
}

export interface LaunchPayload {
  issue_url: string;
  repo_path: string;
  min_workers: number;
  max_workers: number;
  timeout_sec: number;
}

export interface LaunchResponse {
  run_id: string;
  run_done: string;
  manager_session: string;
}

export interface StopResponse {
  run_id: string;
  status: string;
}

export interface SendResponse {
  run_id: string;
  worker: string;
  sent: boolean;
}

export interface TimelineEvent {
  ts: number;
  agent: string;
  role: string;
  status: string;
  session_exists: boolean;
  run_id: string;
}

export interface FlowNode {
  id: string;
  label: string;
  role: string;
  status: string;
  x: number;
  y: number;
}

export interface FlowEdge {
  from: string;
  to: string;
  status: string;
  label: string;
  active: boolean;
}
