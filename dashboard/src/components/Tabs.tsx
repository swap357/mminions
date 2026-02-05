interface Tab {
  id: string;
  label: string;
}

interface Props {
  tabs: Tab[];
  active: string;
  onSelect: (id: string) => void;
}

export function Tabs({ tabs, active, onSelect }: Props) {
  return (
    <div className="flex gap-0 border-b border-border">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t.id)}
          className={`px-4 py-2 text-xs transition-colors ${
            t.id === active
              ? 'text-neutral-200 border-b-2 border-neutral-400'
              : 'text-neutral-500 hover:text-neutral-300'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
