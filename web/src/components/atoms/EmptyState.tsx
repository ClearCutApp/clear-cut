import type { ReactElement, ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  children?: ReactNode;
}

/**
 * Real but empty: a worded sentence for the nothing-here case, with room
 * for the one link that leads out of it. Never a placeholder row and never
 * sample data.
 */
export function EmptyState({ title, children }: EmptyStateProps): ReactElement {
  return (
    <div className="empty-state">
      <p className="empty-state__title">{title}</p>
      {children}
    </div>
  );
}
