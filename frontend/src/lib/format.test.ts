import { describe, expect, test } from "vitest";
import { formatChange, formatMoney, formatQuantity, formatSimDate } from "./format";

describe("format", () => {
  test("money keeps cents and groups thousands", () => {
    expect(formatMoney("10000.00")).toBe("$10,000.00");
    expect(formatMoney("0.1")).toBe("$0.10");
  });

  test("quantity drops trailing zeros", () => {
    expect(formatQuantity("2.0000")).toBe("2");
    expect(formatQuantity("0.2500")).toBe("0.25");
  });

  test("change carries a direction sign, not only color", () => {
    expect(formatChange(0.0523)).toBe("▲ 5.23%");
    expect(formatChange(-0.0523)).toBe("▼ 5.23%");
    expect(formatChange(0)).toBe("0.00%");
  });

  test("sim date is shown in New York market time", () => {
    expect(formatSimDate("2019-01-02T21:00:00Z")).toEqual({ date: "Jan 2, 2019", time: "16:00" });
  });
});
