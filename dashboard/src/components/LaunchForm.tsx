import { useState } from 'react';
import { Rocket, X } from 'lucide-react';
import type { LaunchPayload } from '../lib/types';

interface Props {
  onLaunch: (payload: LaunchPayload) => void;
}

const inputCls =
  'w-full bg-surface-0 border border-border-light rounded px-2 py-1.5 text-xs mono text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-neutral-500';

export function LaunchForm({ onLaunch }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<LaunchPayload>({
    issue_url: '',
    repo_path: '',
    min_workers: 2,
    max_workers: 6,
    timeout_sec: 300,
  });

  const set = <K extends keyof LaunchPayload>(k: K, v: LaunchPayload[K]) =>
    setForm((prev) => ({ ...prev, [k]: v }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onLaunch(form);
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 hover:bg-neutral-700 rounded text-xs text-neutral-300 transition-colors w-full justify-center"
      >
        <Rocket size={12} />
        new run
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-surface-2 rounded border border-border p-4 space-y-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs text-neutral-400 font-medium">launch new run</span>
        <button type="button" onClick={() => setOpen(false)} className="text-neutral-500 hover:text-neutral-300">
          <X size={14} />
        </button>
      </div>
      <input value={form.issue_url} onChange={(e) => set('issue_url', e.target.value)} placeholder="issue url" className={inputCls} required />
      <input value={form.repo_path} onChange={(e) => set('repo_path', e.target.value)} placeholder="repo path (absolute)" className={inputCls} required />
      <div className="flex gap-2">
        <input type="number" value={form.min_workers} onChange={(e) => set('min_workers', +e.target.value)} placeholder="min" className={inputCls} min={2} max={6} />
        <input type="number" value={form.max_workers} onChange={(e) => set('max_workers', +e.target.value)} placeholder="max" className={inputCls} min={2} max={6} />
        <input type="number" value={form.timeout_sec} onChange={(e) => set('timeout_sec', +e.target.value)} placeholder="timeout" className={inputCls} min={60} />
      </div>
      <button
        type="submit"
        className="w-full px-3 py-1.5 bg-green-500/15 hover:bg-green-500/25 text-green-400 rounded text-xs transition-colors"
      >
        launch
      </button>
    </form>
  );
}
