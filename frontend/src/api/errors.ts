/** Error raised for any non-2xx API response; `reason` is the backend's machine-readable code. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly reason: string | null,
    public readonly detail: string | null,
  ) {
    super(reason ?? detail ?? `HTTP ${status}`);
    this.name = "ApiError";
  }

  static from(status: number, body: unknown): ApiError {
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (detail && typeof detail === "object" && "reason" in detail) {
      return new ApiError(status, String((detail as { reason: unknown }).reason), null);
    }
    return new ApiError(status, null, typeof detail === "string" ? detail : null);
  }
}

const REASONS: Record<string, string> = {
  period_limit_exceeded: "This order goes over the limit you set for the current period.",
  insufficient_position: "You don't hold enough shares to sell that many.",
  insufficient_cash: "Not enough cash to cover this order.",
  no_trading_period: "Trading is closed: the session clock is outside every trading period.",
  order_too_large: "This order is too large to process.",
  order_time_mismatch: "The session clock moved while the order was sent. Place it again.",
  period_closed: "That period has already ended, so its limits can't change.",
  portfolio_not_found: "This session has no portfolio for you.",
  limits_required: "Set your limits for this period before the clock can move.",
  session_finished: "This session has ended.",
  not_replay: "Only time machine sessions have playback controls.",
  invalid_state: "Pause the session before stepping.",
  asset_not_in_session: "This stock is not part of the session.",
};

const STATUS_FALLBACK: Record<number, string> = {
  401: "Pick a user to continue.",
  404: "Not found.",
  422: "Some fields are not valid. Check them and try again.",
  501: "Sign-in is not available on this server yet.",
};

/** Plain-language message for an error, suitable for a toast or an inline notice. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.reason && REASONS[error.reason]) return REASONS[error.reason];
    if (error.detail) return error.detail.charAt(0).toUpperCase() + error.detail.slice(1) + ".";
    if (STATUS_FALLBACK[error.status]) return STATUS_FALLBACK[error.status];
    return "Something went wrong on the server. Try again.";
  }
  return "Can't reach the server. Check your connection and try again.";
}
