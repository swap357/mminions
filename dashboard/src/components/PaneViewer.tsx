import { useRef, useEffect } from 'react';

interface Props {
  title: string;
  tail: string;
  maxH?: string;
}

export function PaneViewer({ title, tail, maxH = 'max-h-48' }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [tail]);

  return (
    <div className="bg-surface-0 rounded border border-border">
      <div className="px-3 py-1.5 border-b border-border text-xs text-neutral-500">
        {title}
      </div>
      <div
        ref={ref}
        className={`p-3 ${maxH} overflow-y-auto pane-output text-neutral-300`}
      >
        {tail || <span className="text-neutral-600">no output</span>}
      </div>
    </div>
  );
}
