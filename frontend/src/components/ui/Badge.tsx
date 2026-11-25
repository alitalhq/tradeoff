import type { ReactNode } from "react";

type Tone = "neutral" | "gain" | "loss" | "accent";

const tones: Record<Tone, string> = {
  neutral: "bg-rule/70 text-muted",
  gain: "bg-gain/12 text-gain",
  loss: "bg-loss/12 text-loss",
  accent: "bg-accent/12 text-accent",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
