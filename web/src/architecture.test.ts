import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

import { DEMO_PROJECT } from "./app/demo";

const SRC_DIR = join(import.meta.dirname, ".");
const CLIENT_PATH = join(SRC_DIR, "api", "client.ts");
const DEMO_PATH = join(SRC_DIR, "app", "demo.ts");
const ATOMS_DIR = join(SRC_DIR, "components", "atoms");
const STYLES_DIR = join(SRC_DIR, "styles");

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

function isTestFile(path: string): boolean {
  return /\.test\.tsx?$/.test(path);
}

function sourceFilesUnderSrc(): string[] {
  return listFiles(SRC_DIR).filter(
    (path) => path.endsWith(".ts") || path.endsWith(".tsx"),
  );
}

function relativeNames(paths: string[]): string[] {
  return paths.map((path) => relative(SRC_DIR, path)).sort();
}

describe("api path ownership", () => {
  it("names the API path in client.ts only", () => {
    const offenders = sourceFilesUnderSrc()
      .filter((path) => path !== CLIENT_PATH)
      .filter((path) => namesAnApiPath(readFileSync(path, "utf-8")));

    expect(relativeNames(offenders)).toEqual([]);
  });
});

describe("atom purity", () => {
  it("keeps atoms free of any import from src/api/", () => {
    const importFromApi = /from\s+["'][^"']*\/api\//;

    const offenders = listFiles(ATOMS_DIR)
      .filter((path) => path.endsWith(".tsx") && !isTestFile(path))
      .filter((path) => importFromApi.test(readFileSync(path, "utf-8")));

    expect(relativeNames(offenders)).toEqual([]);
  });
});

/**
 * Rule 4. The demo values are read from `app/demo.ts` itself rather than
 * spelled here, so this file never becomes a second home for them. The
 * jurisdiction code is short enough to occur inside other words, so it
 * only counts when quoted as a whole string; the version is a bare number
 * and cannot be scanned, so `DEMO_PROJECT.version` is its only pin.
 */
function namesADemoLiteral(content: string): boolean {
  const quotedCode = QUOTE_CHARACTERS.map(
    (quote) => quote + DEMO_PROJECT.jurisdictionCode + quote,
  );
  return [DEMO_PROJECT.projectId, DEMO_PROJECT.gcsUri, ...quotedCode].some(
    (literal) => content.includes(literal),
  );
}

describe("demo literal ownership", () => {
  it("keeps the demo project values in app/demo.ts and tests only", () => {
    const offenders = sourceFilesUnderSrc()
      .filter((path) => path !== DEMO_PATH && !isTestFile(path))
      .filter((path) => namesADemoLiteral(readFileSync(path, "utf-8")));

    expect(relativeNames(offenders)).toEqual([]);
  });
});

/**
 * Rule 5, the defect D65's gate cannot see: a class defined in a partial
 * that no component renders. Class tokens come from the partials with
 * comments and `url(...)` payloads stripped. Usage is read from the string
 * literals of non-test `.tsx` files, split on whitespace, with comments
 * stripped first so prose can never vouch for a class. A class is live when
 * its literal is one of those tokens, or when it carries `--` and some token
 * starts with its prefix through `--` (a template modifier such as
 * `state-badge--${state}`).
 *
 * The check is scoped to blocks with at least one live class: a whole block
 * with no consumer yet is a root rule waiting for its component (the plan
 * ships shell and feature roots before their views), while a block in use
 * with dead elements or modifiers is the rot this rule exists to catch.
 */
const CLASS_TOKEN = /\.(-?[a-z][a-z0-9_-]*)/g;
const BLOCK_COMMENT = /\/\*[\s\S]*?\*\//g;
const URL_PAYLOAD = /url\([^)]*\)/g;
const LINE_COMMENT = /(^|\s)\/\/.*$/gm;
const STRING_LITERAL = /"([^"\\\n]*)"|'([^'\\\n]*)'|`([^`\\]*)`/g;

function classesDefinedIn(cssPath: string): string[] {
  const css = readFileSync(cssPath, "utf-8")
    .replace(BLOCK_COMMENT, "")
    .replace(URL_PAYLOAD, "");
  return [...css.matchAll(CLASS_TOKEN)].map((match) => match[1]);
}

function stringTokensIn(tsxPath: string): string[] {
  const source = readFileSync(tsxPath, "utf-8")
    .replace(BLOCK_COMMENT, "")
    .replace(LINE_COMMENT, "");
  return [...source.matchAll(STRING_LITERAL)].flatMap((match) =>
    (match[1] ?? match[2] ?? match[3] ?? "").split(/\s+/).filter(Boolean),
  );
}

function blockOf(className: string): string {
  return className.split(/__|--/)[0];
}

describe("stylesheet liveness", () => {
  it("defines no element or modifier that no component renders", () => {
    const defined = new Set(
      listFiles(STYLES_DIR)
        .filter((path) => path.endsWith(".css"))
        .flatMap(classesDefinedIn),
    );
    const tokens = new Set(
      sourceFilesUnderSrc()
        .filter((path) => path.endsWith(".tsx") && !isTestFile(path))
        .flatMap(stringTokensIn),
    );
    const isLive = (className: string): boolean => {
      if (tokens.has(className)) {
        return true;
      }
      const modifierStart = className.indexOf("--");
      if (modifierStart === -1) {
        return false;
      }
      const prefix = className.slice(0, modifierStart + 2);
      return [...tokens].some((token) => token.startsWith(prefix));
    };
    const liveBlocks = new Set([...defined].filter(isLive).map(blockOf));

    const dead = [...defined].filter(
      (className) => !isLive(className) && liveBlocks.has(blockOf(className)),
    );

    expect(dead.sort()).toEqual([]);
  });
});
