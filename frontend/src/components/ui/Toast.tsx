import { CheckCircle2, CircleAlert, Info } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type Tone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

const DISMISS_AFTER_MS = 5000;

const ToastContext = createContext<{ show: (message: string, tone?: Tone) => void }>({ show: () => {} });

const ICONS = { success: CheckCircle2, error: CircleAlert, info: Info } as const;
const TONES = { success: "text-gain", error: "text-loss", info: "text-accent" } as const;

/** Toasts announce through one polite status region and dismiss themselves after 5 seconds. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const show = useCallback((message: string, tone: Tone = "info") => {
    const id = next.current++;
    setItems((current) => [...current.slice(-2), { id, message, tone }]);
    setTimeout(() => setItems((current) => current.filter((t) => t.id !== id)), DISMISS_AFTER_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-20 z-50 flex flex-col items-end gap-2 md:bottom-6 md:left-auto md:right-6"
      >
        {items.map((t) => {
          const Icon = ICONS[t.tone];
          return (
            <div
              key={t.id}
              className="pointer-events-auto flex max-w-sm items-start gap-2 rounded-md border border-rule bg-raised px-3 py-2 text-sm shadow-sm"
            >
              <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${TONES[t.tone]}`} />
              <span>{t.message}</span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
