import type { ReactElement } from "react";

/**
 * Local to this atom on purpose, the same call `RiskBadge` makes: the mode
 * vocabulary has two consumers today, this file and `api/client.ts`, which is
 * AGENT.md Section 4's duplicate-twice case rather than a shared module. An
 * atom may not import from `src/api/` in any event.
 *
 * `null` is the state before the health endpoint answers. Its path is not
 * named here: `client.ts` owns every endpoint literal, and `architecture.test.ts`
 * counts a quoted path in a comment as naming one.
 */
export type Mode = "mock" | "live";

export interface ModeBannerProps {
  mode: Mode | null;
}

/**
 * Says plainly when the numbers on the page are planted.
 *
 * `CLEARCUT_MODE=mock` serves the fixed scenario in `adapters/demo/scenario.py`
 * (D36), and the SPA used to render it with exactly the confidence it renders a
 * real analysis. Mock mode is a legitimate hedge against a deadline; rendering
 * it silently is what made it read as a deception instead.
 *
 * Renders nothing for `live` and nothing before the answer arrives, so the
 * banner is only ever an admission, never a false alarm over real data.
 */
export function ModeBanner({ mode }: ModeBannerProps): ReactElement | null {
  if (mode !== "mock") {
    return null;
  }
  return (
    <div className="mode-banner" data-testid="mode-banner" role="status">
      <strong className="mode-banner__label">Demo mode</strong>
      <span className="mode-banner__text">
        Every scene, finding and tracker item below comes from a fixed sample.
        No script was analysed and no external service was called.
      </span>
    </div>
  );
}
