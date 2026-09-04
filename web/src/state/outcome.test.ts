import { describe, expect, it } from "vitest";

import { ApiError } from "../api/client";
import { attempt, fail, failureMessage, succeed } from "./outcome";

describe("Outcome", () => {
  it("wraps a value as ok and a message as not ok", () => {
    expect(succeed(3)).toEqual({ ok: true, value: 3 });
    expect(fail("no")).toEqual({ ok: false, message: "no" });
  });
});

describe("failureMessage", () => {
  it("shows the server's own sentence for an ApiError", () => {
    expect(failureMessage(new ApiError(400, "gcs_uri is required"), "x")).toBe(
      "gcs_uri is required",
    );
  });

  it("falls back to the caller's sentence for anything else", () => {
    expect(failureMessage(new TypeError("network"), "The request failed.")).toBe(
      "The request failed.",
    );
  });
});

describe("attempt", () => {
  it("resolves ok with the request's value", async () => {
    await expect(attempt(() => Promise.resolve("v"), "x")).resolves.toEqual({
      ok: true,
      value: "v",
    });
  });

  it("resolves not ok with the mapped message instead of rejecting", async () => {
    const outcome = attempt(
      () => Promise.reject(new ApiError(404, "not found")),
      "x",
    );

    await expect(outcome).resolves.toEqual({ ok: false, message: "not found" });
  });
});
