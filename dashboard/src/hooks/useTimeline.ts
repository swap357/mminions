import { useRef, useEffect } from 'react';
import type { RunStatus, TimelineEvent } from '../lib/types';

export function useTimeline(status: RunStatus | null): TimelineEvent[] {
  const eventsRef = useRef<TimelineEvent[]>([]);
  const seenRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!status?.workers) return;
    const now = Date.now();

    for (const w of status.workers) {
      const key = `${status.run_id}:${w.worker_id}:${w.status}`;
      if (!seenRef.current.has(key)) {
        seenRef.current.add(key);
        eventsRef.current.push({
          ts: now,
          agent: w.worker_id,
          role: w.role,
          status: w.status,
          session_exists: w.session_exists,
          run_id: status.run_id,
        });
      }
    }

    const mKey = `${status.run_id}:manager:${status.run_state}`;
    if (!seenRef.current.has(mKey)) {
      seenRef.current.add(mKey);
      eventsRef.current.push({
        ts: now,
        agent: 'manager',
        role: 'MANAGER',
        status: status.run_state,
        session_exists: status.manager?.session_exists ?? false,
        run_id: status.run_id,
      });
    }
  }, [status]);

  return eventsRef.current;
}
