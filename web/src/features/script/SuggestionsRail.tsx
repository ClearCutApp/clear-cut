import type { ReactElement } from "react";

import { FilterPill } from "../../components/atoms/FilterPill";
import {
  applySuggestionFilter,
  SUGGESTION_FILTERS,
  suggestionCounts,
  type Suggestion,
  type SuggestionFilter,
} from "./model";
import { SuggestionCard } from "./SuggestionCard";

export interface SuggestionsRailProps {
  suggestions: Suggestion[];
  filter: SuggestionFilter;
  onFilterChange: (filter: SuggestionFilter) => void;
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string | null) => void;
}

const FILTER_LABELS: Record<SuggestionFilter, string> = {
  ALL: "All",
  HIGH_RISK: "High risk",
  TO_REVIEW: "To review",
  CONSIDERATIONS: "Considerations",
  CLEARED: "Cleared",
};

/**
 * The rail beside the paper: the chips that narrow the list, then the
 * findings themselves in the order the script reads them. The chip counts
 * come from the whole list, so narrowing it never moves them.
 *
 * Opening a card is the same act as selecting its finding, which is what
 * marks the phrase on the page. Clicking the open one closes it and clears
 * the selection, so a reader can put the script back the way they found it.
 */
export function SuggestionsRail({
  suggestions,
  filter,
  onFilterChange,
  selectedFindingId,
  onSelectFinding,
}: SuggestionsRailProps): ReactElement {
  const counts = suggestionCounts(suggestions);
  const shown = applySuggestionFilter(suggestions, filter);
  return (
    <section className="suggestions" aria-label="Suggestions">
      <div className="suggestions__filters">
        {SUGGESTION_FILTERS.map((value) => (
          <FilterPill
            key={value}
            label={FILTER_LABELS[value]}
            count={counts[value]}
            active={filter === value}
            onClick={() => onFilterChange(value)}
          />
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="suggestions__empty">No findings match this filter.</p>
      ) : (
        <ul className="suggestions__list">
          {shown.map((suggestion) => {
            const id = suggestion.finding.finding_id;
            const selected = id === selectedFindingId;
            return (
              <SuggestionCard
                key={id}
                suggestion={suggestion}
                expanded={selected}
                selected={selected}
                onToggle={() => onSelectFinding(selected ? null : id)}
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}
