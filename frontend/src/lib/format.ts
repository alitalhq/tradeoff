// Values arrive from the API as decimal strings; they are converted to numbers only for display.

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const quantity = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
const percent = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// US equities trade on New York time, so the session clock is shown in that zone.
export const MARKET_TIME_ZONE = "America/New_York";

const simDate = new Intl.DateTimeFormat("en-US", {
  timeZone: MARKET_TIME_ZONE,
  month: "short",
  day: "numeric",
  year: "numeric",
});
const simTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: MARKET_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
});

export function formatMoney(value: string | number): string {
  return money.format(Number(value));
}

export function formatQuantity(value: string | number): string {
  return quantity.format(Number(value));
}

/** A ratio such as 0.0523 shown with an arrow, so direction never depends on color alone. */
export function formatChange(ratio: number): string {
  const text = `${percent.format(Math.abs(ratio) * 100)}%`;
  if (ratio > 0) return `▲ ${text}`;
  if (ratio < 0) return `▼ ${text}`;
  return text;
}

export function formatSimDate(iso: string): { date: string; time: string } {
  const at = new Date(iso);
  return { date: simDate.format(at), time: simTime.format(at) };
}
