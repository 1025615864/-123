import { ReactNode, useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  showCloseButton?: boolean;
  zIndexClass?: string;
}

export default function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = "md",
  showCloseButton = true,
  zIndexClass = "z-[70]",
}: ModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }

    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;

    window.setTimeout(() => {
      const target = closeBtnRef.current ?? dialogRef.current;
      target?.focus?.();
    }, 0);

    return () => {
      restoreFocusRef.current?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const sizeStyles = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-2xl",
    xl: "max-w-4xl",
  };

  return (
    <div
      className={`fixed inset-0 ${zIndexClass} flex items-center justify-center p-4 sm:p-6 animate-fade-in`}
    >
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity duration-200 dark:bg-[#0f0a1e]/70"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={`relative w-full ${sizeStyles[size]} rounded-2xl bg-white border border-slate-200/70 shadow-xl ring-1 ring-slate-900/5 p-7 max-h-[90vh] overflow-y-auto outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-white/[0.03] dark:border-white/[0.08] dark:ring-white/10 dark:backdrop-blur-xl dark:shadow-2xl dark:shadow-black/40 dark:focus-visible:ring-offset-slate-900`}
      >
        {(title || showCloseButton) && (
          <div className="flex items-start justify-between gap-4 mb-6">
            {title && (
              <div>
                <h2 id={titleId} className="text-xl font-bold text-slate-900 dark:text-white">
                  {title}
                </h2>
                {description && (
                  <p id={descriptionId} className="text-sm text-slate-600 mt-1 dark:text-white/55">
                    {description}
                  </p>
                )}
              </div>
            )}
            {showCloseButton && (
              <button
                type="button"
                ref={closeBtnRef}
                onClick={onClose}
                className="p-2 rounded-xl text-slate-500 outline-none transition-all hover:text-slate-900 hover:bg-slate-900/5 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-white/60 dark:hover:text-white dark:hover:bg-white/5 dark:focus-visible:ring-offset-slate-900"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
