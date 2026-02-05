import { useState } from 'react';
import { Send } from 'lucide-react';
import type { WorkerStatus } from '../lib/types';
import { statusColor } from '../lib/status';
import { PaneViewer } from './PaneViewer';

interface Props {
  worker: WorkerStatus;
  runId: string;
  onSend: (runId: string, worker: string, text: string) => void;
}

export function WorkerCard({ worker, runId, onSend }: Props) {
  const [text, setText] = useState('');

  const handleSend = () => {
    if (!text.trim()) return;
    onSend(runId, worker.worker_id, text.trim());
    setText('');
  };

  return (
    <div className="bg-surface-2 rounded border border-border animate-in fade-in">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: statusColor(worker.status) }}
          />
          <span className="text-sm font-medium mono">{worker.worker_id}</span>
          <span className="text-xs text-neutral-500 bg-surface-3 px-1.5 py-0.5 rounded">
            {worker.role}
          </span>
        </div>
        <span className="text-xs text-neutral-500">{worker.status}</span>
      </div>

      <PaneViewer title="output" tail={worker.pane_tail} maxH="max-h-32" />

      {worker.session_exists && (
        <div className="flex gap-2 p-2 border-t border-border">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="send command..."
            className="flex-1 bg-surface-0 border border-border-light rounded px-2 py-1 text-xs mono text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-neutral-500"
          />
          <button
            onClick={handleSend}
            className="px-2 py-1 bg-surface-3 hover:bg-neutral-700 rounded text-xs text-neutral-300 transition-colors"
          >
            <Send size={12} />
          </button>
        </div>
      )}
    </div>
  );
}
