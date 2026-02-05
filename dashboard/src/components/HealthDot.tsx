interface Props {
  healthy: boolean;
}

export function HealthDot({ healthy }: Props) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <div
        className={`w-2 h-2 rounded-full ${healthy ? 'bg-status-running pulse-dot' : 'bg-status-failed'}`}
      />
      <span className="text-neutral-500">
        {healthy ? 'connected' : 'disconnected'}
      </span>
    </div>
  );
}
