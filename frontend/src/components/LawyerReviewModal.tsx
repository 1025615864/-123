import { useEffect, useMemo, useState } from "react";
import { Star } from "lucide-react";
import api from "../api/client";
import { useAppMutation } from "../hooks";
import { Button, Modal, Textarea } from "./ui";

export interface LawyerReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  consultationId: number | null;
  lawyerId: number | null;
  title?: string;
  onSuccess?: () => void;
}

type ReviewResponse = {
  id: number;
  lawyer_id: number;
  consultation_id?: number | null;
  rating: number;
  content?: string | null;
};

export default function LawyerReviewModal({
  isOpen,
  onClose,
  consultationId,
  lawyerId,
  title,
  onSuccess,
}: LawyerReviewModalProps) {
  const [rating, setRating] = useState<number>(5);
  const [content, setContent] = useState<string>("");

  useEffect(() => {
    if (!isOpen) return;
    setRating(5);
    setContent("");
  }, [isOpen]);

  const canSubmit = useMemo(() => {
    if (typeof consultationId !== "number" || consultationId <= 0) return false;
    if (typeof lawyerId !== "number" || lawyerId <= 0) return false;
    if (rating < 1 || rating > 5) return false;
    return true;
  }, [consultationId, lawyerId, rating]);

  const submitMutation = useAppMutation<ReviewResponse, void>({
    mutationFn: async () => {
      if (typeof consultationId !== "number" || typeof lawyerId !== "number") {
        throw new Error("invalid params");
      }
      const res = await api.post("/lawfirm/reviews", {
        lawyer_id: lawyerId,
        consultation_id: consultationId,
        rating,
        content: String(content || "").trim() ? String(content || "").trim() : null,
        is_anonymous: false,
      });
      return (res.data || {}) as ReviewResponse;
    },
    successMessage: "评价已提交",
    errorMessageFallback: "评价提交失败，请稍后重试",
    onSuccess: async () => {
      onSuccess?.();
      onClose();
    },
  });

  const submitting = submitMutation.isPending;

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        if (submitting) return;
        onClose();
      }}
      title={title || "提交评价"}
      description="评分与文字评价将用于展示律师服务质量"
      size="md"
    >
      <div className="space-y-5">
        <div className="space-y-2">
          <div className="text-sm font-medium text-slate-700 dark:text-white/70">评分</div>
          <div className="flex items-center gap-2">
            {Array.from({ length: 5 }).map((_, idx) => {
              const v = idx + 1;
              const active = v <= rating;
              return (
                <button
                  key={v}
                  type="button"
                  className={`p-2 rounded-lg transition ${
                    active
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-slate-300 hover:text-slate-500 dark:text-white/20 dark:hover:text-white/40"
                  }`}
                  onClick={() => {
                    if (submitting) return;
                    setRating(v);
                  }}
                  disabled={submitting}
                  aria-label={`评分 ${v} 星`}
                >
                  <Star className={`h-6 w-6 ${active ? "fill-current" : ""}`} />
                </button>
              );
            })}
            <div className="text-sm text-slate-600 dark:text-white/55">{rating} / 5</div>
          </div>
        </div>

        <Textarea
          label="评价内容（可选）"
          placeholder="写下你的体验，帮助更多用户选择律师..."
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={submitting}
        />

        <div className="flex items-center justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => {
              if (submitting) return;
              onClose();
            }}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            variant="primary"
            isLoading={submitting}
            loadingText="提交中..."
            disabled={!canSubmit || submitting}
            onClick={() => {
              if (!canSubmit || submitting) return;
              submitMutation.mutate();
            }}
          >
            提交
          </Button>
        </div>
      </div>
    </Modal>
  );
}
