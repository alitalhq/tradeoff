import { formatSimDate } from "../lib/format";

interface Period {
  period_no: number;
  starts_at: string;
  ends_at: string;
}

interface SessionClockProps {
  simTime?: string;
  startAt?: string;
  endAt?: string | null;
  status?: SessionStatus;
  periods?: Period[];
}

const STATUS_LABEL = {
  created: "Ready",
  running: "Running",
  paused: "Paused",
  awaiting_limits: "Set limits",
  finished: "Finished",
} as const;

export type SessionStatus = keyof typeof STATUS_LABEL;

/**
 * The session clock: the date the user is trading on, and for replays a rail from start to end
 * with a tick at every trading-period boundary.
 */
export function SessionClock({ simTime, startAt, endAt, status = "created", periods = [] }: SessionClockProps) {
  if (!simTime || !startAt) {
    return <p className="text-sm text-muted">No session open</p>;
  }
  const { date, time } = formatSimDate(simTime);
  const isReplay = Boolean(endAt);
  const now = Date.parse(simTime);
  const start = Date.parse(startAt);
  const span = endAt ? Date.parse(endAt) - start : 0;
  const position = (iso: string) => (span > 0 ? Math.min(100, Math.max(0, ((Date.parse(iso) - start) / span) * 100)) : 0);
  const progress = Math.round(position(simTime));
  const current = periods.find((p) => now >= Date.parse(p.starts_at) && now < Date.parse(p.ends_at));

  return (
    <div className="flex min-w-0 items-center gap-4">
      <div className="flex items-baseline gap-2 whitespace-nowrap">
        <time dateTime={simTime} className="text-xl font-semibold tabular-nums tracking-tight sm:text-2xl">
          {date}
        </time>
        <span className="text-sm tabular-nums text-muted">{time} ET</span>
      </div>

      <div className="hidden min-w-0 flex-1 flex-col gap-1 md:flex">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className={status === "running" ? "text-accent" : undefined}>{isReplay ? STATUS_LABEL[status] : "Live"}</span>
          {current && periods.length > 0 && (
            <span>
              Period {current.period_no} of {periods.length}
            </span>
          )}
        </div>
        {isReplay && (
          <div
            role="progressbar"
            aria-label="Replay progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            className="relative h-1.5 w-full max-w-md rounded-full bg-rule"
          >
            <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${progress}%` }} />
            {periods.slice(1).map((p) => (
              <span
                key={p.period_no}
                aria-hidden
                className="absolute -top-0.5 h-2.5 w-px bg-ink/40"
                style={{ left: `${position(p.starts_at)}%` }}
              />
            ))}
          </div>
        )}
      </div>

      {isReplay && (
        // Phones hide the labelled rail; this hairline along the header edge keeps the progress visible.
        <div aria-hidden className="absolute inset-x-0 bottom-0 h-0.5 bg-rule md:hidden">
          <div className="h-full bg-accent" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
}
