import type { ReactElement } from "react";

export interface FilterPillProps {
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}

/**
 * One toggle in a filter row. `aria-pressed` carries the state for
 * assistive technology; the modifier class carries it for the eye.
 */
export function FilterPill({
  label,
  count,
  active,
  onClick,
}: FilterPillProps): ReactElement {
  return (
    <button
      type="button"
      className={active ? "filter-pill filter-pill--active" : "filter-pill"}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
      {count !== undefined && <span className="filter-pill__count">{count}</span>}
    </button>
  );
}
