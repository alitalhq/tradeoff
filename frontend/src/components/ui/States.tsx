import type { UseQueryResult } from "@tanstack/react-query";
import { CircleAlert, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { describeError } from "../../api/errors";
import { Button } from "./Button";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-muted">
      <LoaderCircle aria-hidden className="size-4 animate-spin" />
      {label}
    </span>
  );
}

/** Empty states point to the next action rather than describing absence. */
export function EmptyState({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 py-8">
      <p className="text-sm text-muted">{title}</p>
      {action}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-md border border-loss/40 bg-loss/5 px-3 py-2 text-sm">
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-loss" />
      <span className="flex-1">{describeError(error)}</span>
      {onRetry && (
        <Button size="sm" variant="quiet" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Renders the loading, error and empty states of a query so screens only handle data. */
export function QueryView<T>({ query, isEmpty, empty, children }: {
  query: UseQueryResult<T>;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <Spinner />;
  if (query.isError) return <ErrorNotice error={query.error} onRetry={() => query.refetch()} />;
  if (empty && isEmpty?.(query.data)) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
