import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

/**
 * Modal built on <dialog>: the browser handles focus trapping, Escape and the inert backdrop.
 * Focus returns to whatever opened it.
 */
export function Modal({ open, title, onClose, children, footer }: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      const opener = document.activeElement as HTMLElement | null;
      dialog.showModal();
      return () => opener?.focus?.();
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  if (!open) return null;
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-lg border border-rule bg-raised p-0 text-ink backdrop:bg-ink/40"
    >
      <header className="flex items-center justify-between border-b border-rule px-5 py-3">
        <h2 id={titleId} className="text-base font-semibold">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="grid size-9 cursor-pointer place-items-center rounded-md text-muted hover:bg-rule/60 hover:text-ink"
        >
          <X aria-hidden className="size-4" />
        </button>
      </header>
      <div className="px-5 py-4">{children}</div>
      {footer && <footer className="flex justify-end gap-2 border-t border-rule px-5 py-3">{footer}</footer>}
    </dialog>
  );
}
