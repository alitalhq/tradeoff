import type { ReactNode } from "react";

/** A titled panel. Headings are sentence case; actions sit on the right of the title row. */
export function Card({ title, actions, children, className = "" }: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-rule bg-raised ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-rule px-4 py-2.5">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
