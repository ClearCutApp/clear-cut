import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const SRC_DIR = join(import.meta.dirname, ".");
const CLIENT_PATH = join(SRC_DIR, "api", "client.ts");
const ATOMS_DIR = join(SRC_DIR, "components", "atoms");

/**
 * Built by concatenation, not written as a literal, so this file itself
 * never contains the substring it searches for. That keeps the "no other
 * file" scan honest instead of special-casing this file out of its own
 * check.
 *
 * The match requires a quote character immediately before the segment, so
 * it catches a real endpoint literal opening a string (GET /api/tracker,
 * written as a quote right up against the leading slash) while leaving
 * alone a relative import specifier such as one reaching into ../api/client
 * (the quote there sits before the two dots, not before the segment) and
 * prose that merely mentions the src/api/ directory.
 */
const API_PATH_SEGMENT = ["/", "api", "/"].join("");
const QUOTE_CHARACTERS = ['"', "'", "`"];

function namesAnApiPath(content: string): boolean {
  return QUOTE_CHARACTERS.some((quote) =>
    content.includes(quote + API_PATH_SEGMENT),
  );
}

function listFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const fullPath = join(dir, entry);
    if (statSync(fullPath).isDirectory()) {
      return listFiles(fullPath);
    }
    return [fullPath];
  });
}

function sourceFilesUnderSrc(): string[] {
  return listFiles(SRC_DIR).filter(
    (path) => path.endsWith(".ts") || path.endsWith(".tsx"),
  );
}

describe("api path ownership", () => {
  it("names the API path in client.ts only", () => {
    const offenders = sourceFilesUnderSrc()
      .filter((path) => path !== CLIENT_PATH)
      .filter((path) => namesAnApiPath(readFileSync(path, "utf-8")));

    expect(offenders.map((path) => relative(SRC_DIR, path))).toEqual([]);
  });
});

describe("atom purity", () => {
  it("keeps atoms free of any import from src/api/", () => {
    const importFromApi = /from\s+["'][^"']*\/api\//;

    const offenders = listFiles(ATOMS_DIR)
      .filter((path) => path.endsWith(".tsx") && !path.endsWith(".test.tsx"))
      .filter((path) => importFromApi.test(readFileSync(path, "utf-8")));

    expect(offenders.map((path) => relative(SRC_DIR, path))).toEqual([]);
  });
});
