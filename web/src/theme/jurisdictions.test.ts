import { describe, expect, it } from "vitest";

import { JURISDICTIONS, jurisdictionName } from "./jurisdictions";

describe("JURISDICTIONS", () => {
  it("offers exactly ten codes with Argentina first", () => {
    expect(JURISDICTIONS).toHaveLength(10);
    expect(JURISDICTIONS[0]).toEqual({ code: "AR", name: "Argentina" });
    expect(new Set(JURISDICTIONS.map((entry) => entry.code)).size).toBe(10);
  });
});

describe("jurisdictionName", () => {
  it("maps a known code to its display name", () => {
    expect(jurisdictionName("GB")).toBe("United Kingdom");
    expect(jurisdictionName("KR")).toBe("South Korea");
  });

  it("echoes an unknown code instead of blanking it", () => {
    expect(jurisdictionName("ZZ")).toBe("ZZ");
  });

  it("does not resolve inherited object keys as jurisdictions", () => {
    expect(jurisdictionName("constructor")).toBe("constructor");
  });
});
