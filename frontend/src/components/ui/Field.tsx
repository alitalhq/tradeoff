import { useId, type InputHTMLAttributes } from "react";

export function Field({ label, error, ...input }: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm outline-none focus:border-accent"
        {...input}
      />
      {error && <span className="text-xs text-loss">{error}</span>}
    </div>
  );
}
