import { useId, type InputHTMLAttributes } from "react";

/** Labelled input with hint and error shown under the field, never as placeholder text. */
export function Field({ label, hint, error, className = "", ...input }: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  const described = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={described}
        className="min-h-10 rounded-md border border-rule bg-raised px-3 text-sm tabular-nums aria-invalid:border-loss"
        {...input}
      />
      {error ? (
        <span id={`${id}-error`} className="text-xs text-loss">
          {error}
        </span>
      ) : (
        hint && (
          <span id={`${id}-hint`} className="text-xs text-muted">
            {hint}
          </span>
        )
      )}
    </div>
  );
}
