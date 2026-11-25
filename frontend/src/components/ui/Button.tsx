import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "quiet" | "danger";
type Size = "md" | "sm";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:brightness-110",
  quiet: "bg-transparent text-ink hover:bg-rule/60",
  danger: "bg-loss text-white hover:brightness-110",
};

const sizes: Record<Size, string> = {
  md: "min-h-10 px-4 text-sm",
  sm: "min-h-8 px-3 text-xs",
};

export function Button({
  variant = "primary",
  size = "md",
  busy = false,
  className = "",
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; busy?: boolean }) {
  return (
    <button
      className={`inline-flex cursor-pointer items-center justify-center gap-2 rounded-md font-medium transition-[filter,background-color] duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...props}
    >
      {children}
    </button>
  );
}
