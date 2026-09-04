/**
 * The jurisdictions the analyze form offers, code to display name. Words
 * only: the theme maps enums to labels and never to colors. An unknown
 * code echoes itself so a server value the list has not caught up with is
 * still shown rather than blanked.
 */
const NAMES = {
  AR: "Argentina",
  US: "United States",
  ES: "Spain",
  MX: "Mexico",
  CA: "Canada",
  FR: "France",
  GB: "United Kingdom",
  IN: "India",
  BR: "Brazil",
  KR: "South Korea",
} as const;

export type JurisdictionCode = keyof typeof NAMES;

export interface Jurisdiction {
  code: JurisdictionCode;
  name: string;
}

export const JURISDICTIONS: readonly Jurisdiction[] = (
  Object.keys(NAMES) as JurisdictionCode[]
).map((code) => ({ code, name: NAMES[code] }));

function isKnown(code: string): code is JurisdictionCode {
  return Object.hasOwn(NAMES, code);
}

export function jurisdictionName(code: string): string {
  return isKnown(code) ? NAMES[code] : code;
}
