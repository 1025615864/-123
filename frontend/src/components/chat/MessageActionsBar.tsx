import { useMemo, useState } from "react";
import {
  Copy,
  MoreVertical,
  RotateCcw,
  Star,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { Modal } from "../ui";

export interface MessageActionsBarProps {
  disabled?: boolean;
  canCopy?: boolean;
  canRegenerate?: boolean;
  canFavorite?: boolean;
  canRate?: boolean;
  favorited?: boolean;
  rated?: number | null;
  rateLoading?: boolean;
  onCopy?: () => void;
  onCopyWithReferences?: () => void;
  onRegenerate?: () => void;
  onToggleFavorite?: () => void;
  onRateGood?: () => void;
  onRateBad?: () => void;
}

export default function MessageActionsBar({
  disabled = false,
  canCopy = true,
  canRegenerate = true,
  canFavorite = true,
  canRate = true,
  favorited = false,
  rated = null,
  rateLoading = false,
  onCopy,
  onCopyWithReferences,
  onRegenerate,
  onToggleFavorite,
  onRateGood,
  onRateBad,
}: MessageActionsBarProps) {
  const [moreOpen, setMoreOpen] = useState(false);

  const disableCopy = disabled || !canCopy || !onCopy;
  const disableCopyWithRefs = disabled || !canCopy || !onCopyWithReferences;
  const disableFavorite = disabled || !canFavorite || !onToggleFavorite;
  const disableRegenerate = disabled || !canRegenerate || !onRegenerate;
  const disableRate = disabled || !canRate || rateLoading;

  const actionClassName =
    "inline-flex items-center gap-1.5 text-xs transition-colors disabled:opacity-60 disabled:cursor-not-allowed";

  const copyClassName = useMemo(
    () =>
      `${actionClassName} text-slate-500 hover:text-blue-600 dark:text-slate-400 dark:hover:text-blue-400`,
    [actionClassName]
  );

  const favoriteClassName = useMemo(() => {
    if (favorited) {
      return `${actionClassName} text-amber-600 font-medium dark:text-amber-400`;
    }
    return `${actionClassName} text-slate-500 hover:text-amber-600 dark:text-slate-400 dark:hover:text-amber-400`;
  }, [actionClassName, favorited]);

  const goodClassName = useMemo(() => {
    if (rated === 3) {
      return `${actionClassName} text-blue-600 font-medium dark:text-blue-400`;
    }
    return `${actionClassName} text-slate-500 hover:text-blue-600 dark:text-slate-400 dark:hover:text-blue-400`;
  }, [actionClassName, rated]);

  const badClassName = useMemo(() => {
    if (rated === 1) {
      return `${actionClassName} text-red-600 font-medium dark:text-red-400`;
    }
    return `${actionClassName} text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400`;
  }, [actionClassName, rated]);

  const regenClassName = useMemo(
    () =>
      `${actionClassName} text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400`,
    [actionClassName]
  );

  const moreClassName = useMemo(
    () =>
      `${actionClassName} text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200`,
    [actionClassName]
  );

  return (
    <div className="flex flex-wrap items-center gap-4 pt-2">
      <button
        type="button"
        onClick={onCopy}
        className={copyClassName}
        disabled={disableCopy}
        aria-label="复制回答"
      >
        <Copy className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">复制</span>
      </button>

      <button
        type="button"
        disabled={disableFavorite}
        onClick={onToggleFavorite}
        className={favoriteClassName}
        aria-label={favorited ? "已收藏" : "收藏"}
      >
        <Star className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">{favorited ? "已收藏" : "收藏"}</span>
      </button>

      <button
        type="button"
        disabled={disableRate}
        onClick={onRateGood}
        className={goodClassName}
        aria-label="好评"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">好评</span>
      </button>

      <button
        type="button"
        disabled={disableRate}
        onClick={onRateBad}
        className={badClassName}
        aria-label="差评"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">差评</span>
      </button>

      <button
        type="button"
        disabled={disableRegenerate}
        onClick={onRegenerate}
        className={regenClassName}
        aria-label="重新生成"
      >
        <RotateCcw className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">重来</span>
      </button>

      <button
        type="button"
        onClick={() => setMoreOpen(true)}
        className={moreClassName}
        aria-label="更多"
        disabled={disabled}
      >
        <MoreVertical className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">更多</span>
      </button>

      <Modal
        isOpen={moreOpen}
        onClose={() => setMoreOpen(false)}
        title="更多操作"
        description="对当前回答执行更多操作"
        size="sm"
      >
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => {
              setMoreOpen(false);
              onCopy?.();
            }}
            disabled={disableCopy}
            className="w-full px-4 py-3 rounded-xl text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 transition disabled:opacity-60 disabled:cursor-not-allowed dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
          >
            复制回答
          </button>

          <button
            type="button"
            onClick={() => {
              setMoreOpen(false);
              onCopyWithReferences?.();
            }}
            disabled={disableCopyWithRefs}
            className="w-full px-4 py-3 rounded-xl text-sm font-medium bg-slate-100 text-slate-900 hover:bg-slate-200 transition disabled:opacity-60 disabled:cursor-not-allowed dark:bg-slate-800 dark:text-white dark:hover:bg-slate-700"
          >
            复制（含法条引用）
          </button>

          <button
            type="button"
            onClick={() => {
              setMoreOpen(false);
              onRegenerate?.();
            }}
            disabled={disableRegenerate}
            className="w-full px-4 py-3 rounded-xl text-sm font-medium bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100 transition disabled:opacity-60 disabled:cursor-not-allowed dark:bg-emerald-500/10 dark:text-emerald-200 dark:border-emerald-500/20 dark:hover:bg-emerald-500/15"
          >
            重新生成（填充上一条提问）
          </button>
        </div>
      </Modal>
    </div>
  );
}
