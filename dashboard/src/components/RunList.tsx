import { NavLink } from 'react-router-dom';

interface Props {
  runs: string[];
}

export function RunList({ runs }: Props) {
  return (
    <div className="flex flex-col gap-0.5">
      {runs.map((r) => (
        <NavLink
          key={r}
          to={`/runs/${r}`}
          className={({ isActive }) =>
            `text-left px-3 py-2 rounded text-xs mono truncate transition-colors ${
              isActive
                ? 'bg-surface-3 text-white'
                : 'text-neutral-400 hover:bg-surface-2 hover:text-neutral-200'
            }`
          }
        >
          {r}
        </NavLink>
      ))}
      {runs.length === 0 && (
        <p className="text-neutral-600 text-xs px-3 py-2">no runs</p>
      )}
    </div>
  );
}
