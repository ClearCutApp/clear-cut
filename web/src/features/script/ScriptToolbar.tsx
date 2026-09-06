import {
  Bold,
  Code,
  Heading1,
  Heading2,
  Italic,
  List,
  ListOrdered,
  Underline,
} from "lucide-react";
import type { ReactElement } from "react";

export interface ScriptToolbarProps {
  words: number;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  canZoomIn: boolean;
  canZoomOut: boolean;
}

interface FormatControl {
  label: string;
  Icon: typeof Bold;
}

const FORMAT_CONTROLS: FormatControl[] = [
  { label: "Bold", Icon: Bold },
  { label: "Italic", Icon: Italic },
  { label: "Underline", Icon: Underline },
  { label: "Heading 1", Icon: Heading1 },
  { label: "Heading 2", Icon: Heading2 },
  { label: "Bulleted list", Icon: List },
  { label: "Numbered list", Icon: ListOrdered },
  { label: "Code", Icon: Code },
];

/**
 * The reason every formatting control is disabled, said once where the
 * controls are rather than left for a reader to discover by clicking.
 */
const NO_EDITING_REASON =
  "The script is read back from the analysis. This API serves a script version to read and has no endpoint that writes one, so nothing here can change the text.";

/**
 * The bar above the paper: formatting, the word count, and zoom.
 *
 * The formatting controls are drawn and disabled. They are the shape of
 * the screen the design asks for, and the honest state of a control with
 * no endpoint behind it -- the same discipline as `ModeBanner` and the
 * sidebar's unavailable entries. Wiring them to a local edit would show a
 * writer changes that no reload would keep.
 *
 * The word count and the zoom are not in that position: both are computed
 * from what is already on screen, so both work.
 */
export function ScriptToolbar({
  words,
  zoom,
  onZoomIn,
  onZoomOut,
  canZoomIn,
  canZoomOut,
}: ScriptToolbarProps): ReactElement {
  return (
    <div className="script-toolbar">
      <div
        className="script-toolbar__format"
        role="group"
        aria-label="Formatting"
        aria-describedby="script-toolbar-reason"
      >
        {FORMAT_CONTROLS.map(({ label, Icon }) => (
          <button
            key={label}
            type="button"
            className="script-toolbar__button"
            aria-label={label}
            disabled
          >
            <Icon size={14} aria-hidden="true" />
          </button>
        ))}
      </div>
      <p className="script-toolbar__reason" id="script-toolbar-reason">
        {NO_EDITING_REASON}
      </p>
      <div className="script-toolbar__meters">
        <p className="script-toolbar__words">{words.toLocaleString("en-US")} words</p>
        <div className="script-toolbar__zoom" role="group" aria-label="Zoom">
          <button
            type="button"
            className="script-toolbar__button"
            aria-label="Zoom out"
            onClick={onZoomOut}
            disabled={!canZoomOut}
          >
            -
          </button>
          <span className="script-toolbar__level">{zoom}%</span>
          <button
            type="button"
            className="script-toolbar__button"
            aria-label="Zoom in"
            onClick={onZoomIn}
            disabled={!canZoomIn}
          >
            +
          </button>
        </div>
      </div>
    </div>
  );
}
