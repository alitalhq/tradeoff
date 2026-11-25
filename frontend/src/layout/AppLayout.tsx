import { NavLink, Outlet } from "react-router";

const NAV = [
  { to: "/live", label: "Live" },
  { to: "/replay", label: "Time Machine" },
  { to: "/arena", label: "Arena" },
  { to: "/portfolio", label: "Portfolio" },
];

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-12 items-center border-b border-border bg-surface-raised px-4">
        <span className="font-semibold tracking-tight">TradeOff</span>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <nav className="flex gap-1 border-b border-border p-2 md:w-48 md:flex-col md:border-b-0 md:border-r">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-accent/15 text-accent" : "text-muted hover:text-text"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
