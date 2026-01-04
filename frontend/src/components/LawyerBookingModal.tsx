import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { X, Calendar, Phone, FileText, Send } from "lucide-react";
import api from "../api/client";
import { useAppMutation, useToast } from "../hooks";
import { useAuth } from "../contexts/AuthContext";
import { Card, Button, Input } from "./ui";
import { getApiErrorMessage } from "../utils";

interface Lawyer {
  id: number;
  name: string;
  title?: string;
  specialties?: string;
  consultation_fee?: number;
}

interface LawyerBookingModalProps {
  lawyer: Lawyer;
  onClose: () => void;
  onSuccess?: () => void;
}

type ConsultationCreateResponse = {
  id: number;
  payment_order_no?: string | null;
  payment_status?: string | null;
  payment_amount?: number | null;
};

type ThirdPartyPayResponse = {
  pay_url?: string;
};

const CASE_TYPES = [
  "劳动纠纷",
  "合同纠纷",
  "婚姻家庭",
  "房产纠纷",
  "消费维权",
  "交通事故",
  "借贷纠纷",
  "刑事辩护",
  "其他",
];

export default function LawyerBookingModal({
  lawyer,
  onClose,
  onSuccess,
}: LawyerBookingModalProps) {
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    subject: "",
    category: "",
    description: "",
    contact_phone: "",
    preferred_time: "",
  });

  const submitMutation = useAppMutation<ConsultationCreateResponse, void>({
    mutationFn: async (_: void) => {
      const res = await api.post("/lawfirm/consultations", {
        lawyer_id: lawyer.id,
        subject: formData.subject,
        category: formData.category,
        description: formData.description,
        contact_phone: formData.contact_phone,
        preferred_time: formData.preferred_time
          ? new Date(formData.preferred_time).toISOString()
          : null,
      });
      return (res.data || {}) as ConsultationCreateResponse;
    },
    errorMessageFallback: "预约失败，请稍后重试",
    onSuccess: async (data) => {
      const orderNo = String(data?.payment_order_no || "").trim();
      const paymentStatus = String(data?.payment_status || "")
        .trim()
        .toLowerCase();
      const needPayNow = orderNo && paymentStatus === "pending";

      onSuccess?.();

      if (!needPayNow) {
        toast.success("预约成功！律师会尽快与您联系");
        const go = window.confirm("预约成功！去查看我的预约吗？");
        onClose();
        if (go) {
          navigate("/orders?tab=consultations");
        }
        return;
      }

      const goPay = window.confirm(
        "预约已提交，需要支付费用才能确认。现在使用余额支付吗？"
      );
      if (!goPay) {
        toast.success("预约已提交，请尽快完成支付以确认预约");
        onClose();
        navigate("/orders?tab=consultations");
        return;
      }

      const useBalance = window.confirm(
        "确定使用余额支付吗？取消将使用支付宝支付"
      );

      if (useBalance) {
        try {
          await api.post(`/payment/orders/${encodeURIComponent(orderNo)}/pay`, {
            payment_method: "balance",
          });
          toast.success("支付成功，等待律师确认");
          onClose();
          navigate("/orders?tab=consultations");
        } catch (err: any) {
          toast.error(getApiErrorMessage(err, "支付失败，请稍后重试"));
          onClose();
          navigate("/orders?tab=consultations");
        }
        return;
      }

      try {
        const res = await api.post(
          `/payment/orders/${encodeURIComponent(orderNo)}/pay`,
          {
            payment_method: "alipay",
          }
        );
        const payUrl = String(
          ((res.data || {}) as ThirdPartyPayResponse)?.pay_url || ""
        ).trim();
        if (!payUrl) {
          toast.error("未获取到支付链接");
          onClose();
          navigate("/orders?tab=consultations");
          return;
        }
        window.open(payUrl, "_blank", "noopener,noreferrer");
        toast.success("已打开支付宝支付页面，请支付后等待律师确认");
        onClose();
        navigate("/orders?tab=consultations");
      } catch (err: any) {
        toast.error(getApiErrorMessage(err, "获取支付链接失败，请稍后重试"));
        onClose();
        navigate("/orders?tab=consultations");
      }
    },
  });

  const handleSubmit = async () => {
    if (!isAuthenticated) {
      toast.error("请先登录后再预约");
      return;
    }

    if (!formData.subject || !formData.category || !formData.contact_phone) {
      toast.error("请填写必填项");
      return;
    }

    if (submitMutation.isPending) return;
    submitMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 dark:bg-black/60">
      <Card
        variant="surface"
        padding="none"
        className="w-full max-w-lg overflow-hidden rounded-2xl"
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200/70 bg-gradient-to-r from-amber-500/10 to-orange-500/10 dark:border-white/10">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              预约律师咨询
            </h2>
            <p className="text-sm text-slate-600 mt-1 dark:text-white/50">
              预约 {lawyer.name} {lawyer.title && `(${lawyer.title})`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-900/5 rounded-lg transition-colors dark:hover:bg-white/10"
          >
            <X className="h-5 w-5 text-slate-500 dark:text-white/50" />
          </button>
        </div>

        {/* 表单 */}
        <div className="p-6 space-y-5 max-h-[60vh] overflow-y-auto">
          {/* 咨询费用提示 */}
          {lawyer.consultation_fee && lawyer.consultation_fee > 0 && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
              <p className="text-amber-700 text-sm dark:text-amber-400">
                💰 咨询费用：¥{lawyer.consultation_fee}/次
              </p>
            </div>
          )}

          {/* 咨询主题 */}
          <Input
            label="咨询主题 *"
            value={formData.subject}
            onChange={(e) =>
              setFormData({ ...formData, subject: e.target.value })
            }
            placeholder="简要描述您的问题"
            icon={FileText}
          />

          {/* 案件类型 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              案件类型 *
            </label>
            <div className="flex flex-wrap gap-2">
              {CASE_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setFormData({ ...formData, category: type })}
                  className={`px-3 py-1.5 rounded-full text-sm transition-all ${
                    formData.category === type
                      ? "bg-amber-600 text-white dark:bg-amber-500"
                      : "bg-slate-900/5 text-slate-700 hover:bg-slate-50 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10"
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* 问题描述 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              问题描述
            </label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={3}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none resize-none focus:border-amber-600/50 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:focus:border-amber-500/50"
              placeholder="详细描述您的情况和问题..."
            />
          </div>

          {/* 联系电话 */}
          <Input
            label="联系电话 *"
            value={formData.contact_phone}
            onChange={(e) =>
              setFormData({ ...formData, contact_phone: e.target.value })
            }
            placeholder="请输入您的手机号"
            icon={Phone}
          />

          {/* 期望时间 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              <Calendar className="h-4 w-4 inline mr-2" />
              期望咨询时间
            </label>
            <input
              type="datetime-local"
              value={formData.preferred_time}
              onChange={(e) =>
                setFormData({ ...formData, preferred_time: e.target.value })
              }
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none focus:border-amber-600/50 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:focus:border-amber-500/50"
            />
          </div>

          {!isAuthenticated && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
              <p className="text-red-600 text-sm dark:text-red-400">
                ⚠️ 请先{" "}
                <a href="/login" className="underline">
                  登录
                </a>{" "}
                后再预约咨询
              </p>
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex gap-3 px-6 py-4 border-t border-slate-200/70 dark:border-white/10">
          <Button variant="outline" onClick={onClose} className="flex-1">
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitMutation.isPending || !isAuthenticated}
            isLoading={submitMutation.isPending}
            className="flex-1"
          >
            <Send className="h-4 w-4 mr-2" />
            提交预约
          </Button>
        </div>
      </Card>
    </div>
  );
}
