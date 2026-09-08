import { useState } from "react";
import { AskView } from "./AskView";
import { OverviewView } from "./OverviewView";
/** Entry is chosen once per visit; rotating a phone never discards a question. */
export function ProjectEntryView() {
  const [mobile] = useState(() => window.matchMedia?.("(max-width: 767px)").matches ?? false);
  return mobile ? <AskView /> : <OverviewView />;
}
