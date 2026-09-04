import type { ReactElement } from "react";

export interface ErrorNoticeProps {
  message: string | null;
}

/**
 * A failure the reader can see, announced as an alert. Renders nothing
 * without a message so callers pass their error state straight through.
 */
export function ErrorNotice({ message }: ErrorNoticeProps): ReactElement | null {
  if (message === null || message.length === 0) {
    return null;
  }
  return (
    <p className="error-notice" role="alert">
      {message}
    </p>
  );
}
