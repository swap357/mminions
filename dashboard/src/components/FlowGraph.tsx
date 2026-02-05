import type { FlowNode, FlowEdge } from '../lib/types';
import { statusColor } from '../lib/status';

interface Props {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export function FlowGraph({ nodes, edges }: Props) {
  if (nodes.length === 0) {
    return <div className="text-neutral-600 text-xs p-4">no flow data</div>;
  }

  const W = 620;
  const H = 260;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 260 }}>
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="10"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#555" />
          </marker>
        </defs>

        {edges.map((e, i) => {
          const from = nodes.find((n) => n.id === e.from);
          const to = nodes.find((n) => n.id === e.to);
          if (!from || !to) return null;
          const color = e.active
            ? '#3b82f6'
            : e.status === 'failed'
              ? '#ef4444'
              : e.status === 'finished'
                ? '#22c55e'
                : '#444';
          const thickness = e.active ? 2 : 1.5;
          return (
            <g key={i}>
              <line
                x1={from.x}
                y1={from.y + 20}
                x2={to.x}
                y2={to.y - 20}
                stroke={color}
                strokeWidth={thickness}
                markerEnd="url(#arrow)"
                opacity={0.7}
              />
              <text
                x={(from.x + to.x) / 2 + 8}
                y={(from.y + to.y) / 2 + 4}
                fill="#666"
                fontSize="9"
                fontFamily="JetBrains Mono, monospace"
              >
                {e.label}
              </text>
            </g>
          );
        })}

        {nodes.map((n) => {
          const fill = statusColor(n.status);
          return (
            <g key={n.id}>
              <rect
                x={n.x - 36}
                y={n.y - 16}
                width={72}
                height={32}
                rx={6}
                fill="#1a1a1a"
                stroke={fill}
                strokeWidth={1.5}
              />
              <circle cx={n.x - 22} cy={n.y} r={3} fill={fill} />
              <text
                x={n.x - 12}
                y={n.y + 4}
                fill="#ddd"
                fontSize="11"
                fontFamily="JetBrains Mono, monospace"
              >
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex gap-4 mt-3 text-xs text-neutral-500">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> active
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> finished
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> failed
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" /> timeout
        </span>
      </div>
    </div>
  );
}
