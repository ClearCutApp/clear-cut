import { useLocale } from "../../state/LocaleContext";
import type { ReactElement } from "react";

export interface NeedsReviewBadgeProps {
  needsReview: boolean;
}

/**
 * The word `NEEDS_REVIEW` next to its color, or nothing. The flag is never
 * cleared by any endpoint, so once it shows it stays; the badge is an
 * admission, not a status the reader can act on here.
 */
export function NeedsReviewBadge({
  needsReview,
}: NeedsReviewBadgeProps): ReactElement | null {
  const { text } = useLocale();
  if (!needsReview) {
    return null;
  }
  return <span className="needs-review-badge">{text("NEEDS_REVIEW", "REQUIERE REVISIÓN")}</span>;
}
