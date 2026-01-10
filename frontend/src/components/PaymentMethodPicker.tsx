import { CreditCard, Wallet } from "lucide-react";
import { Button } from "./ui";

export type PaymentMethod = "balance" | "alipay" | "ikunpay";

export type PaymentMethodOption = {
  method: PaymentMethod;
  label: string;
  description?: string;
  enabled?: boolean;
  disabledReason?: string;
};

export interface PaymentMethodPickerProps {
  options: PaymentMethodOption[];
  busy?: boolean;
  onSelect: (method: PaymentMethod) => void;
  onCancel: () => void;
  onBack?: () => void;
  backLabel?: string;
}

function optionIcon(method: PaymentMethod) {
  if (method === "balance") return Wallet;
  return CreditCard;
}

export default function PaymentMethodPicker({
  options,
  busy = false,
  onSelect,
  onCancel,
  onBack,
  backLabel = "返回修改",
}: PaymentMethodPickerProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {(Array.isArray(options) ? options : []).map((opt) => {
          const enabled = opt.enabled !== false;
          const Icon = optionIcon(opt.method);
          const reason = !enabled ? String(opt.disabledReason || "").trim() : "";
          return (
            <button
              key={opt.method}
              type="button"
              disabled={!enabled || busy}
              onClick={() => {
                if (!enabled || busy) return;
                onSelect(opt.method);
              }}
              className={`w-full text-left rounded-xl border px-4 py-3 transition-all outline-none focus-visible:ring-2 focus-visible:ring-blue-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${
                enabled && !busy
                  ? "border-slate-200/70 bg-white hover:bg-slate-50 active:scale-[0.99] dark:border-white/10 dark:bg-white/[0.03] dark:hover:bg-white/[0.06]"
                  : "border-slate-200/60 bg-slate-50 opacity-60 cursor-not-allowed dark:border-white/10 dark:bg-white/[0.02]"
              }`}
            >
              <div className="flex items-start gap-3">
                <div
                  className={`mt-0.5 h-9 w-9 rounded-xl flex items-center justify-center ${
                    enabled && !busy
                      ? "bg-slate-900/5 text-slate-700 dark:bg-white/5 dark:text-white/75"
                      : "bg-slate-900/5 text-slate-500 dark:bg-white/5 dark:text-white/40"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      {opt.label}
                    </div>
                    {!enabled && reason ? (
                      <div className="text-xs text-slate-500 dark:text-white/45">
                        {reason}
                      </div>
                    ) : null}
                  </div>
                  {opt.description ? (
                    <div className="mt-1 text-xs text-slate-600 dark:text-white/55">
                      {opt.description}
                    </div>
                  ) : null}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {onBack ? (
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            fullWidth
            onClick={() => {
              if (busy) return;
              onBack();
            }}
            disabled={busy}
          >
            {backLabel}
          </Button>
          <Button
            type="button"
            variant="secondary"
            fullWidth
            onClick={() => {
              if (busy) return;
              onCancel();
            }}
            disabled={busy}
          >
            取消
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          variant="secondary"
          fullWidth
          onClick={() => {
            if (busy) return;
            onCancel();
          }}
          disabled={busy}
        >
          取消
        </Button>
      )}
    </div>
  );
}
