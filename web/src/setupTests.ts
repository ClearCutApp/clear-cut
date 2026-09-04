import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

const originalFetch = globalThis.fetch;

// Every test starts with an empty browser: the recent-projects list lives in
// localStorage and a fetch stub on the global, and either would otherwise
// leak from one test into the next.
afterEach(() => {
  localStorage.clear();
  globalThis.fetch = originalFetch;
});
