import { describe, expect, test } from "vitest";
import { ApiError, describeError } from "./errors";

describe("ApiError", () => {
  test("reads the rejection reason from a 409 body", () => {
    const err = ApiError.from(409, { detail: { reason: "period_limit_exceeded" } });
    expect(err.status).toBe(409);
    expect(err.reason).toBe("period_limit_exceeded");
  });

  test("describes known reasons in plain words", () => {
    expect(describeError(ApiError.from(409, { detail: { reason: "insufficient_position" } }))).toBe(
      "You don't hold enough shares to sell that many.",
    );
  });

  test("falls back to the server detail, then to a generic message", () => {
    expect(describeError(ApiError.from(404, { detail: "session not found" }))).toBe("Session not found.");
    expect(describeError(ApiError.from(500, null))).toBe("Something went wrong on the server. Try again.");
  });
});
