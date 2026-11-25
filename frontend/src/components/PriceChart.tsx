import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Bar } from "../api/client";

export interface TradeMarker {
  time: string;
  side: "buy" | "sell";
  price: string;
}

interface PriceChartProps {
  bars: Bar[];
  markers?: TradeMarker[];
  height?: number;
}

const toSeconds = (iso: string) => Math.floor(Date.parse(iso) / 1000) as UTCTimestamp;

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Candlestick chart. Prices arrive as strings and are converted to numbers only for drawing. */
export function PriceChart({ bars, markers = [], height = 360 }: PriceChartProps) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markerApi = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    if (!container.current) return;
    chart.current = createChart(container.current, {
      height,
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: cssVar("--muted", "#5d6673") },
      grid: { vertLines: { visible: false }, horzLines: { color: cssVar("--border", "#e2e5ea") } },
    });
    series.current = chart.current.addSeries(CandlestickSeries, {
      upColor: cssVar("--gain", "#128a55"),
      downColor: cssVar("--loss", "#d23c3c"),
      wickUpColor: cssVar("--gain", "#128a55"),
      wickDownColor: cssVar("--loss", "#d23c3c"),
      borderVisible: false,
    });
    markerApi.current = createSeriesMarkers(series.current, []);
    return () => {
      chart.current?.remove();
      chart.current = null;
      series.current = null;
      markerApi.current = null;
    };
  }, [height]);

  useEffect(() => {
    series.current?.setData(
      bars.map((b) => ({
        time: toSeconds(b.bar_start),
        open: Number(b.open),
        high: Number(b.high),
        low: Number(b.low),
        close: Number(b.close),
      })),
    );
    markerApi.current?.setMarkers(
      markers.map((m) => ({
        time: toSeconds(m.time),
        position: m.side === "buy" ? "belowBar" : "aboveBar",
        shape: m.side === "buy" ? "arrowUp" : "arrowDown",
        color: m.side === "buy" ? cssVar("--gain", "#128a55") : cssVar("--loss", "#d23c3c"),
        text: m.price,
      })),
    );
    chart.current?.timeScale().fitContent();
  }, [bars, markers]);

  return <div ref={container} className="w-full" style={{ height }} />;
}
