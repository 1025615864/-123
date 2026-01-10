import { ReactNode, useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

export interface SideBySideModalProps {
  isOpen: boolean;
  onClose: () => void;

  leftTitle?: string;
  leftDescription?: string;
  left: ReactNode;

  rightTitle?: string;
  rightDescription?: string;
  right?: ReactNode;
  onRightClose?: () => void;

  zIndexClass?: string;
}

export default function SideBySideModal({
  isOpen,
  onClose,
  leftTitle,
  leftDescription,
  left,
  rightTitle,
  rightDescription,
  right,
  onRightClose,
  zIndexClass = "z-[70]",
}: SideBySideModalProps) {
  const leftTitleId = useId();
  const leftDescriptionId = useId();
  const rightTitleId = useId();
  const rightDescriptionId = useId();

  const leftDialogRef = useRef<HTMLDivElement | null>(null);
  const rightDialogRef = useRef<HTMLDivElement | null>(null);
  const leftCloseBtnRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  const showRight = Boolean(right);

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
      if (e.key !== "Escape") return;
      if (!isOpen) return;
      if (showRight && onRightClose) {
        onRightClose();
        return;
      }
      onClose();
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose, onRightClose, showRight]);

  useEffect(() => {
    if (!isOpen) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;

    window.setTimeout(() => {
      const target = showRight ? rightDialogRef.current : leftCloseBtnRef.current;
      (target ?? leftDialogRef.current)?.focus?.();
    }, 0);

    return () => {
      restoreFocusRef.current?.focus?.();
    };
  }, [isOpen, showRight]);

  if (!isOpen) return null;

  return (
    <div className={`fixed inset-0 ${zIndexClass} flex items-center justify-center p-4 sm:p-6 animate-fade-in`}>
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity duration-200 dark:bg-[#0f0a1e]/70"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className={`relative w-full flex flex-col md:flex-row items-stretch justify-center gap-4`}>
        <div
          ref={leftDialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={leftTitle ? leftTitleId : undefined}
          aria-describedby={leftDescription ? leftDescriptionId : undefined}
          tabIndex={-1}
          className={`relative w-full md:max-w-md rounded-2xl bg-white border border-slate-200/70 shadow-xl ring-1 ring-slate-900/5 p-7 max-h-[90vh] overflow-y-auto outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-white/[0.03] dark:border-white/[0.08] dark:ring-white/10 dark:backdrop-blur-xl dark:shadow-2xl dark:shadow-black/40 dark:focus-visible:ring-offset-slate-900 ${
            showRight ? "md:-translate-x-6" : ""
          }`}
        >
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              {leftTitle ? (
                <h2 id={leftTitleId} className="text-xl font-bold text-slate-900 dark:text-white">
                  {leftTitle}
                </h2>
              ) : null}
              {leftDescription ? (
                <p id={leftDescriptionId} className="text-sm text-slate-600 mt-1 dark:text-white/55">
                  {leftDescription}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              ref={leftCloseBtnRef}
              onClick={onClose}
              className="p-2 rounded-xl text-slate-500 outline-none transition-all hover:text-slate-900 hover:bg-slate-900/5 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-white/60 dark:hover:text-white dark:hover:bg-white/5 dark:focus-visible:ring-offset-slate-900"
              aria-label="关闭"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {left}
        </div>

        {showRight ? (
          <div
            ref={rightDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={rightTitle ? rightTitleId : undefined}
            aria-describedby={rightDescription ? rightDescriptionId : undefined}
            tabIndex={-1}
            className={`relative w-full md:max-w-md rounded-2xl bg-white border border-slate-200/70 shadow-xl ring-1 ring-slate-900/5 p-7 max-h-[90vh] overflow-y-auto outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-white/[0.03] dark:border-white/[0.08] dark:ring-white/10 dark:backdrop-blur-xl dark:shadow-2xl dark:shadow-black/40 dark:focus-visible:ring-offset-slate-900 md:translate-x-6`}
          >
            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                {rightTitle ? (
                  <h2 id={rightTitleId} className="text-xl font-bold text-slate-900 dark:text-white">
                    {rightTitle}
                  </h2>
                ) : null}
                {rightDescription ? (
                  <p id={rightDescriptionId} className="text-sm text-slate-600 mt-1 dark:text-white/55">
                    {rightDescription}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => {
                  if (onRightClose) {
                    onRightClose();
                  } else {
                    onClose();
                  }
                }}
                className="p-2 rounded-xl text-slate-500 outline-none transition-all hover:text-slate-900 hover:bg-slate-900/5 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:text-white/60 dark:hover:text-white dark:hover:bg-white/5 dark:focus-visible:ring-offset-slate-900"
                aria-label="关闭"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {right}
          </div>
        ) : null}
      </div>
    </div>
  );
}
