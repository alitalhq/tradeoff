/* Generated from contracts/ws-schema.json. Do not edit. */

export type WsSchema = ClockMessage | BarMessage | NewsMessage | FillMessage | PeriodMessage;
export type SimTime = string;
export type Status = "created" | "running" | "paused" | "finished";
export type Type = "clock";
export type AssetId = number;
export type AssetId1 = number;
export type BarEnd = string;
export type BarStart = string;
export type Close = string;
export type High = string;
export type Low = string;
export type Open = string;
export type Timeframe = string;
export type Volume = number;
export type Type1 = "bar";
export type Headline = string;
export type Id = number;
export type PublishedAt = string;
export type Source = string;
export type Summary = string;
export type Url = string;
export type Type2 = "news";
export type OrderId = number;
export type Price = string | null;
export type Reason = string | null;
export type Status1 = "filled" | "rejected";
export type Type3 = "fill";
export type AwaitingLimits = boolean;
export type EndsAt = string;
export type PeriodNo = number;
export type StartsAt = string;
export type Type4 = "period";

export interface ClockMessage {
  sim_time: SimTime;
  status: Status;
  type: Type;
}
export interface BarMessage {
  asset_id: AssetId;
  bar: Bar;
  type: Type1;
}
export interface Bar {
  asset_id: AssetId1;
  bar_end: BarEnd;
  bar_start: BarStart;
  close: Close;
  high: High;
  low: Low;
  open: Open;
  timeframe: Timeframe;
  volume: Volume;
}
export interface NewsMessage {
  item: NewsItem;
  type: Type2;
}
export interface NewsItem {
  headline: Headline;
  id: Id;
  published_at: PublishedAt;
  source: Source;
  summary: Summary;
  url: Url;
}
export interface FillMessage {
  order_id: OrderId;
  price: Price;
  reason: Reason;
  status: Status1;
  type: Type3;
}
export interface PeriodMessage {
  awaiting_limits: AwaitingLimits;
  ends_at: EndsAt;
  period_no: PeriodNo;
  starts_at: StartsAt;
  type: Type4;
}
