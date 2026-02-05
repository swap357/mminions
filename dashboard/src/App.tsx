import { Outlet, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchHealth, fetchRuns, postLaunch } from './lib/api';
import type { LaunchPayload } from './lib/types';
import { HealthDot } from './components/HealthDot';
import { RunList } from './components/RunList';
import { LaunchForm } from './components/LaunchForm';

export default function App() {
  const navigate = useNavigate();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 2500,
  });

  const { data: runs } = useQuery({
    queryKey: ['runs'],
    queryFn: fetchRuns,
    refetchInterval: 2500,
  });

  const handleLaunch = async (payload: LaunchPayload) => {
    const res = await postLaunch(payload);
    if (res?.run_id) navigate(`/runs/${res.run_id}`);
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-1">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold tracking-tight text-neutral-200">mminions</h1>
          <span className="text-xs text-neutral-600">dashboard</span>
        </div>
        <HealthDot healthy={health?.ok === true} />
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 border-r border-border bg-surface-1 flex flex-col">
          <div className="px-3 py-3 border-b border-border flex items-center justify-between">
            <span className="text-xs text-neutral-500 font-medium">
              runs ({runs?.count ?? 0})
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-1">
            <RunList runs={runs?.runs ?? []} />
          </div>
          <div className="p-3 border-t border-border">
            <LaunchForm onLaunch={handleLaunch} />
          </div>
        </aside>

        <main className="flex-1 flex flex-col overflow-hidden bg-surface-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
