import type { ReactNode } from "react";

type Tone = "neutral" | "gain" | "loss" | "accent";

const tones: Record<Tone, string> = {
  neutral: "bg-border text-muted",
  gain: "bg-gain/15 text-gain",
  loss: "bg-loss/15 text-loss",
  accent: "bg-accent/15 text-accent",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
