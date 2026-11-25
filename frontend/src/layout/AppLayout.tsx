import { useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, History, Radio, Swords } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import type { Schemas } from "../api/client";
import { queryKeys, useSession } from "../api/hooks";
import { useSessionSocket } from "../api/ws";
import { SessionClock } from "../components/SessionClock";
import { useActiveSession } from "../session/ActiveSession";
import { DevUserSwitcher } from "./DevUserSwitcher";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { to: "/live", label: "Live", icon: Radio },
  { to: "/replay", label: "Time Machine", icon: History },
  { to: "/arena", label: "Arena", icon: Swords },
  { to: "/portfolio", label: "Portfolio", icon: BriefcaseBusiness },
];

/** Keeps the cached session in step with clock messages pushed over the socket. */
function LiveSessionClock({ sessionId }: { sessionId: number }) {
  const client = useQueryClient();
  const session = useSession(sessionId);
  useSessionSocket(sessionId, (message) => {
    if (message.type !== "clock") return;
    client.setQueryData<Schemas["SessionOut"]>(queryKeys.session(sessionId), (current) =>
      current ? { ...current, sim_time: message.sim_time, status: message.status } : current,
    );
  });
  const data = session.data;
  return (
    <SessionClock
      simTime={data?.sim_time}
      startAt={data?.start_at}
      endAt={data?.end_at}
      status={data?.status as "created" | "running" | "paused" | "finished" | undefined}
      periods={data?.periods}
    />
  );
}

export function AppLayout() {
  const { sessionId } = useActiveSession();

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-raised focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-rule bg-raised px-4">
        <span className="shrink-0 text-base font-semibold tracking-tight">TradeOff</span>
        <div className="min-w-0 flex-1">
          {sessionId !== null ? <LiveSessionClock sessionId={sessionId} /> : <SessionClock />}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {import.meta.env.DEV && (
            <div className="hidden sm:block">
              <DevUserSwitcher />
            </div>
          )}
          <ThemeToggle />
        </div>
      </header>

      <div className="flex flex-1">
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-30 flex border-t border-rule bg-raised md:static md:w-52 md:flex-col md:gap-0.5 md:border-r md:border-t-0 md:p-2"
        >
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs md:min-h-10 md:flex-none md:flex-row md:justify-start md:gap-2.5 md:rounded-md md:px-3 md:text-sm ${
                  isActive ? "text-accent md:bg-accent/10" : "text-muted hover:text-ink md:hover:bg-rule/50"
                }`
              }
            >
              <Icon aria-hidden className="size-5 md:size-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <main id="main" className="min-w-0 flex-1 p-4 pb-20 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
