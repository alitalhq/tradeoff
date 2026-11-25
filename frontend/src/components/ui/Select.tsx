import { ChevronDown } from "lucide-react";
import { useId, type SelectHTMLAttributes } from "react";

export interface Option {
  value: string;
  label: string;
}

/** Native select (keyboard and screen-reader behaviour for free) styled to match Field. */
export function Select({ label, options, hint, className = "", ...select }: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: Option[];
  hint?: string;
}) {
  const id = useId();
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          aria-describedby={hint ? `${id}-hint` : undefined}
          className="min-h-10 w-full cursor-pointer appearance-none rounded-md border border-rule bg-raised pl-3 pr-9 text-sm"
          {...select}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
      </div>
      {hint && (
        <span id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </span>
      )}
    </div>
  );
}
