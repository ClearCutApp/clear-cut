import type { BibleFact, Category, NerLabel } from "../api/client";

/**
 * Enum values as the words a reader sees. Type-only import from the client
 * so the maps stay exhaustive: a new server enum value fails this file's
 * build instead of rendering as a raw token.
 */
export const CATEGORY_LABELS: Record<Category, string> = {
  INDUSTRIAL_PROPERTY: "Industrial property",
  COPYRIGHT_WORKS: "Copyright works",
  PERSONALITY_IMAGE: "Personality and image",
  INTEGRATED_VISUAL: "Integrated visual",
  LOCATIONS_PERMITS: "Locations and permits",
  SPECIAL_SYMBOLS: "Special symbols",
  CONTINUITY: "Continuity",
  POLICY: "Policy",
};

export const NER_LABELS: Record<NerLabel, string> = {
  BRAND: "Brand",
  MUSIC_EXISTING: "Existing music",
  MUSIC_ORIGINAL: "Original music",
  ART_LIT: "Art and literature",
  MEDIA_AV: "Audiovisual media",
  TALENT_CHARACTER: "Talent or character",
  REAL_PERSON: "Real person",
  PROPS_DESIGN: "Props and design",
  LOCATION_PRIV: "Private location",
  LOCATION_PUB: "Public location",
  SPECIAL_SYMBOL: "Special symbol",
};

export const FACT_KIND_LABELS: Record<BibleFact["kind"], string> = {
  LORE: "Bible fact",
  POLICY: "Policy",
};
