import { X } from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  type ReactElement,
  type ReactNode,
  type RefObject,
} from "react";
import { Link } from "react-router";

import type { Finding, TrackerItem, TrackerState } from "../../api/client";
import { ErrorNotice } from "../../components/atoms/ErrorNotice";
import { NeedsReviewBadge } from "../../components/atoms/NeedsReviewBadge";
import { RiskBadge } from "../../components/atoms/RiskBadge";
import { StateBadge } from "../../components/atoms/StateBadge";
import { FindingFacts } from "./FindingFacts";
import { ItemActions } from "./ItemActions";
import { TrackerFacts } from "./TrackerFacts";

export interface ItemPanelFrameProps {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
}

/** Focus lands on the close button each time a new title opens, and
 * Escape closes for as long as the dialog is mounted. */
function useDialogBehavior(
  title: string,
  onClose: () => void,
): RefObject<HTMLButtonElement | null> {
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButton.current?.focus();
  }, [title]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return closeButton;
}

/**
 * The dialog itself: a titled aside with a close button, a backdrop that
 * closes it (drawn only below the wide breakpoint, where the panel is a
 * bottom sheet), Escape to close, and focus on the close button whenever
 * a new title opens. The host uses it for the states before an item can
 * be shown; `ItemDetailPanel` fills it with the item.
 */
export function ItemPanelFrame({
  title,
  subtitle,
  onClose,
  children,
}: ItemPanelFrameProps): ReactElement {
  const titleId = useId();
  const closeButton = useDialogBehavior(title, onClose);
  return (
    <>
      <div className="item-panel__backdrop" aria-hidden="true" onClick={onClose} />
      <aside className="item-panel" role="dialog" aria-labelledby={titleId}>
        <header className="item-panel__header">
          <div className="item-panel__identity">
            <h2 id={titleId} className="item-panel__title">
              {title}
            </h2>
            {subtitle !== undefined && <p className="item-panel__document">{subtitle}</p>}
          </div>
          <button
            ref={closeButton}
            type="button"
            className="item-panel__close"
            aria-label="Close"
            onClick={onClose}
          >
            <X aria-hidden="true" size={18} />
          </button>
        </header>
        {children}
      </aside>
    </>
  );
}

export interface ItemDetailPanelProps {
  item: TrackerItem;
  /** Null after a reload: the analysis lives in the session only. */
  finding: Finding | null;
  jurisdictionName: string;
  pending: boolean;
  error: string | null;
  onStateChange: (state: TrackerState) => void;
  onDraftEmail: () => void;
  onNotify: () => void;
  onClose: () => void;
}

/**
 * One tracker item in full: identity and badges, the finding's facts when
 * the analysis is in session (else the honest sentence and the way to run
 * one), the tracker's facts with the state select, the two implemented
 * actions, and the outcome of a failed mutation where the reader acted.
 * Presentational: every change goes up through a callback.
 */
export function ItemDetailPanel({
  item,
  finding,
  jurisdictionName,
  pending,
  error,
  onStateChange,
  onDraftEmail,
  onNotify,
  onClose,
}: ItemDetailPanelProps): ReactElement {
  const analyzePath = `/projects/${encodeURIComponent(item.project_id)}/analyze`;
  return (
    <ItemPanelFrame title={item.finding_id} subtitle={item.required_document} onClose={onClose}>
      <div className="item-panel__badges">
        {finding !== null && <RiskBadge risk={finding.risk_level} />}
        <StateBadge state={item.state} />
        <NeedsReviewBadge needsReview={item.needs_review} />
      </div>
      {finding !== null ? (
        <FindingFacts finding={finding} jurisdictionName={jurisdictionName} />
      ) : (
        <p className="item-panel__note">
          Finding details are available after an analysis runs in this session.{" "}
          <Link to={analyzePath}>Run analysis</Link>
        </p>
      )}
      <TrackerFacts item={item} pending={pending} onStateChange={onStateChange} />
      <ItemActions pending={pending} onDraftEmail={onDraftEmail} onNotify={onNotify} />
      <ErrorNotice message={error} />
    </ItemPanelFrame>
  );
}
