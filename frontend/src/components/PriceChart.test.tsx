import { render } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

const setData = vi.fn();
vi.mock("lightweight-charts", () => ({
  CandlestickSeries: {},
  createChart: () => ({
    addSeries: () => ({ setData }),
    applyOptions: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove: vi.fn(),
  }),
  createSeriesMarkers: () => ({ setMarkers: vi.fn() }),
}));

import { PriceChart } from "./PriceChart";

describe("PriceChart", () => {
  test("PriceChart renders without bars", () => {
    const { container } = render(<PriceChart bars={[]} />);
    expect(container.firstChild).toBeInTheDocument();
    expect(setData).toHaveBeenCalledWith([]);
  });

  test("converts string prices to numbers for drawing only", () => {
    render(
      <PriceChart
        bars={[{ asset_id: 1, timeframe: "1d", bar_start: "2019-01-02T14:30:00Z", bar_end: "2019-01-02T21:00:00Z", open: "100.5000", high: "101.0000", low: "99.0000", close: "100.0000", volume: 10 }]}
      />,
    );
    expect(setData).toHaveBeenLastCalledWith([{ time: 1546439400, open: 100.5, high: 101, low: 99, close: 100 }]);
  });
});
