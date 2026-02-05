import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Square } from 'lucide-react';
import { fetchStatus, postStop, postSend } from '../lib/api';
import { statusColor } from '../lib/status';
import { useTimeline } from '../hooks/useTimeline';
import { useFlowGraph } from '../hooks/useFlowGraph';
import { SummaryBar } from '../components/SummaryBar';
import { PaneViewer } from '../components/PaneViewer';
import { WorkerCard } from '../components/WorkerCard';
import { Tabs } from '../components/Tabs';
import { TimelineView } from '../components/TimelineView';
import { FlowGraph } from '../components/FlowGraph';

const tabs = [
  { id: 'status', label: 'Status' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'flow', label: 'Flow Graph' },
];

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [tab, setTab] = useState('status');

  const { data: status, error } = useQuery({
    queryKey: ['status', runId],
    queryFn: () => fetchStatus(runId!),
    refetchInterval: 2500,
    enabled: !!runId,
  });

  const timeline = useTimeline(status ?? null);
  const { nodes, edges } = useFlowGraph(status ?? null);

  const handleStop = async () => {
    if (runId) await postStop(runId);
  };

  const handleSend = async (rid: string, worker: string, text: string) => {
    await postSend(rid, worker, text);
  };

  if (!runId) {
    return (
      <div className="flex-1 flex items-center justify-center text-neutral-600 text-sm">
        select a run or launch a new one
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-1">
        <div className="flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full ${status?.run_state === 'running' ? 'pulse-dot' : ''}`}
            style={{ backgroundColor: statusColor(status?.run_state ?? 'unknown') }}
          />
          <span className="mono text-sm font-medium">{runId}</span>
          <span className="text-xs text-neutral-500">{status?.run_state ?? '...'}</span>
        </div>
        {status?.run_state === 'running' && (
          <button
            onClick={handleStop}
            className="flex items-center gap-1 px-3 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded text-xs transition-colors"
          >
            <Square size={10} />
            stop
          </button>
        )}
      </div>

      <Tabs tabs={tabs} active={tab} onSelect={setTab} />

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded px-3 py-2 text-xs text-red-400">
            {String(error)}
          </div>
        )}

        {tab === 'status' && status && (
          <>
            <SummaryBar summary={status.summary} />

            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-neutral-400">manager</span>
                {status.manager?.issue_url && (
                  <a
                    href={status.manager.issue_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:underline truncate max-w-md"
                  >
                    {status.manager.issue_url}
                  </a>
                )}
              </div>
              <PaneViewer
                title={status.manager?.session_name || 'manager'}
                tail={status.manager?.pane_tail ?? ''}
              />
            </div>

            <div>
              <div className="text-xs font-medium text-neutral-400 mb-2">workers</div>
              <div className="space-y-2">
                {(status.workers ?? []).map((w) => (
                  <WorkerCard key={w.worker_id} worker={w} runId={runId} onSend={handleSend} />
                ))}
                {(!status.workers || status.workers.length === 0) && (
                  <div className="text-neutral-600 text-xs">no workers</div>
                )}
              </div>
            </div>

            {status.decision && Object.keys(status.decision).length > 0 && (
              <div>
                <div className="text-xs font-medium text-neutral-400 mb-2">decision</div>
                <pre className="bg-surface-2 rounded border border-border p-3 text-xs mono text-neutral-300 overflow-x-auto">
                  {JSON.stringify(status.decision, null, 2)}
                </pre>
              </div>
            )}

            {status.run_done && Object.keys(status.run_done).length > 0 && (
              <div>
                <div className="text-xs font-medium text-neutral-400 mb-2">run result</div>
                <pre className="bg-surface-2 rounded border border-border p-3 text-xs mono text-neutral-300 overflow-x-auto">
                  {JSON.stringify(status.run_done, null, 2)}
                </pre>
              </div>
            )}
          </>
        )}

        {tab === 'timeline' && (
          <div>
            <div className="text-xs text-neutral-500 mb-3">
              agent activity timeline — bars show status transitions observed during polling
            </div>
            <div className="bg-surface-1 rounded border border-border">
              <TimelineView events={timeline} />
            </div>
          </div>
        )}

        {tab === 'flow' && (
          <div>
            <div className="text-xs text-neutral-500 mb-3">
              agent flow graph — manager → worker handoffs, colored by status
            </div>
            <div className="bg-surface-1 rounded border border-border p-4">
              <FlowGraph nodes={nodes} edges={edges} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
