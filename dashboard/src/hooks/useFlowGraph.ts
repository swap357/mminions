import { useMemo } from 'react';
import type { RunStatus, FlowNode, FlowEdge } from '../lib/types';

export function useFlowGraph(status: RunStatus | null): { nodes: FlowNode[]; edges: FlowEdge[] } {
  return useMemo(() => {
    if (!status?.workers) return { nodes: [], edges: [] };

    const nodes: FlowNode[] = [];
    const edges: FlowEdge[] = [];

    nodes.push({
      id: 'manager',
      label: 'Manager',
      role: 'MANAGER',
      status: status.run_state,
      x: 0,
      y: 0,
    });

    const workers = status.workers;
    workers.forEach((w) => {
      nodes.push({
        id: w.worker_id,
        label: w.worker_id,
        role: w.role,
        status: w.status,
        x: 0,
        y: 0,
      });
      edges.push({
        from: 'manager',
        to: w.worker_id,
        status: w.status,
        label: w.role,
        active: w.session_exists,
      });
    });

    const cx = 300;
    const cy = 60;
    nodes[0].x = cx;
    nodes[0].y = cy;

    const workerCount = workers.length;
    if (workerCount > 0) {
      const spread = Math.min(500, workerCount * 120);
      const startX = cx - spread / 2;
      workers.forEach((_, i) => {
        nodes[i + 1].x =
          workerCount === 1
            ? cx
            : startX + (spread / (workerCount - 1)) * i;
        nodes[i + 1].y = 180;
      });
    }

    return { nodes, edges };
  }, [status]);
}
