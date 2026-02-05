import type { StatusSummary } from '../lib/types';

interface Props {
  summary: StatusSummary;
}

const items: { key: keyof StatusSummary; label: string; color: string }[] = [
  { key: 'total', label: 'total', color: 'text-neutral-300' },
  { key: 'active', label: 'active', color: 'text-blue-400' },
  { key: 'finished', label: 'finished', color: 'text-green-400' },
  { key: 'failed', label: 'failed', color: 'text-red-400' },
  { key: 'timeout', label: 'timeout', color: 'text-yellow-400' },
];

export function SummaryBar({ summary }: Props) {
  return (
    <div className="flex gap-4 text-xs">
      {items.map((i) => (
        <div key={i.key} className="flex items-center gap-1">
          <span className="text-neutral-500">{i.label}</span>
          <span className={`mono font-medium ${i.color}`}>{summary[i.key]}</span>
        </div>
      ))}
    </div>
  );
}
