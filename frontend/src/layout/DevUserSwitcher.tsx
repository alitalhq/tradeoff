import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DEV_USER_KEY, devUserId } from "../api/client";

/** Development only: picks which user the X-User-Id header impersonates until real auth exists. */
export function DevUserSwitcher() {
  const client = useQueryClient();
  const [value, setValue] = useState(() => devUserId() ?? "");

  return (
    <form
      aria-label="Switch dev user"
      className="flex items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        try {
          localStorage.setItem(DEV_USER_KEY, value.trim());
        } catch {
          return;
        }
        client.invalidateQueries();
      }}
    >
      <label htmlFor="dev-user" className="text-xs text-muted">
        Dev user id
      </label>
      <input
        id="dev-user"
        inputMode="numeric"
        pattern="[0-9]*"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        className="h-8 w-16 rounded-md border border-rule bg-raised px-2 text-sm tabular-nums"
      />
    </form>
  );
}
