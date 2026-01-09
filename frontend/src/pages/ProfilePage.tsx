import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  User,
  Loader2,
  Mail,
  Phone,
  Wallet,
  CreditCard,
  Camera,
  Save,
  Shield,
  FileText,
  MessageSquare,
  Heart,
  Star,
  Crown,
  Clock,
  Lock,
  Eye,
  EyeOff,
  Calendar,
  Bell,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Edit,
  Trash2,
  Sparkles,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { useAppMutation, useToast } from "../hooks";
import {
  Card,
  Button,
  Input,
  Modal,
  EmptyState,
  FadeInImage,
  Pagination,
  Textarea,
  Badge,
  ListSkeleton,
  Skeleton,
} from "../components/ui";
import PageHeader from "../components/PageHeader";
import PaymentMethodModal, {
  type PaymentMethod,
} from "../components/PaymentMethodModal";
import { useTheme } from "../contexts/ThemeContext";
import type { Post } from "../types";
import { getApiErrorMessage } from "../utils";
import { queryKeys } from "../queryKeys";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  type PricingPackItem = { count: number; price: number };
  type PricingResp = {
    vip: { days: number; price: number };
    packs: {
      ai_chat: PricingPackItem[];
      document_generate: PricingPackItem[];
    };
  };

  type BalanceResp = {
    balance: number;
    frozen: number;
    total_recharged: number;
    total_consumed: number;
  };

  type BalanceTxItem = {
    id: number;
    type: string;
    amount: number;
    balance_after: number;
    description: string | null;
    created_at: string;
  };

  type BalanceTxListResp = {
    items: BalanceTxItem[];
    total: number;
  };

  type PaymentChannelStatus = {
    alipay_configured: boolean;
    wechatpay_configured: boolean;
    ikunpay_configured: boolean;
    available_methods: string[];
  };

  type UserQuotaDailyResponse = {
    day: string;
    ai_chat_limit: number;
    ai_chat_used: number;
    ai_chat_remaining: number;
    document_generate_limit: number;
    document_generate_used: number;
    document_generate_remaining: number;
    ai_chat_pack_remaining: number;
    document_generate_pack_remaining: number;
    is_vip_active: boolean;
  };

  const pricingQuery = useQuery({
    queryKey: ["payment-pricing"],
    queryFn: async () => {
      const res = await api.get("/payment/pricing");
      return res.data as PricingResp;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const quotasQuery = useQuery({
    queryKey: queryKeys.userMeQuotas(),
    queryFn: async () => {
      const res = await api.get("/user/me/quotas");
      return res.data as UserQuotaDailyResponse;
    },
    enabled: Boolean(user),
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const balanceQuery = useQuery({
    queryKey: ["payment-balance"],
    queryFn: async () => {
      const res = await api.get("/payment/balance");
      return res.data as BalanceResp;
    },
    enabled: Boolean(user),
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const channelStatusQuery = useQuery({
    queryKey: queryKeys.paymentChannelStatus(),
    queryFn: async () => {
      const res = await api.get("/payment/channel-status");
      return (res.data || {}) as PaymentChannelStatus;
    },
    enabled: Boolean(user),
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const vipPlan = pricingQuery.data?.vip;
  const vipDays = Number(vipPlan?.days || 30);
  const vipPrice = Number(vipPlan?.price || 29);

  const isEmailVerified = user?.email_verified === true;
  const isPhoneVerified = user?.phone_verified === true;

  const vipExpiresAt = useMemo(() => {
    const raw = user?.vip_expires_at;
    if (!raw) return null;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return null;
    return d;
  }, [user?.vip_expires_at]);

  const isVipActive = useMemo(() => {
    if (!vipExpiresAt) return false;
    return vipExpiresAt.getTime() > Date.now();
  }, [vipExpiresAt]);

  const buyVipMutation = useAppMutation<
    any,
    { payment_method: "balance" | "alipay" | "ikunpay" }
  >({
    mutationFn: async ({ payment_method }) => {
      const createRes = await api.post("/payment/orders", {
        order_type: "vip",
        amount: vipPrice,
        title: "VIP会员",
        description: "VIP会员",
      });
      const orderNo = String(createRes.data?.order_no || "").trim();
      if (!orderNo) throw new Error("未获取到订单号");

      const payRes = await api.post(
        `/payment/orders/${encodeURIComponent(orderNo)}/pay`,
        {
          payment_method,
        }
      );

      return { order_no: orderNo, ...(payRes.data || {}) };
    },
    errorMessageFallback: "开通失败，请稍后重试",
    disableErrorToast: true,
  });

  const handleBuyVip = () => {
    if (!user) return;
    if (buyVipMutation.isPending) return;

    navigate("/vip");
  };

  const requestEmailVerificationMutation = useAppMutation<any, void>({
    mutationFn: async () => {
      const res = await api.post("/user/email-verification/request");
      return res.data;
    },
    errorMessageFallback: "发送失败，请稍后重试",
  });

  const handleRequestEmailVerification = () => {
    if (!user) return;
    if (isEmailVerified) {
      toast.success("邮箱已验证");
      return;
    }
    if (requestEmailVerificationMutation.isPending) return;
    requestEmailVerificationMutation.mutate(undefined, {
      onSuccess: async (data) => {
        const verifyUrl = String((data as any)?.verify_url || "").trim();
        if (verifyUrl) {
          window.open(verifyUrl, "_blank", "noopener,noreferrer");
          toast.success("已打开验证链接（开发环境）");
        } else {
          toast.success("验证邮件已发送，请前往邮箱完成验证");
        }
        await refreshUser();
      },
    });
  };

  const [showBalanceTxModal, setShowBalanceTxModal] = useState(false);
  const [txPage, setTxPage] = useState(1);
  const txPageSize = 10;

  const balanceTxQuery = useQuery({
    queryKey: [
      "payment-balance-transactions",
      { page: txPage, pageSize: txPageSize },
    ],
    queryFn: async () => {
      const res = await api.get("/payment/balance/transactions", {
        params: { page: txPage, page_size: txPageSize },
      });
      return res.data as BalanceTxListResp;
    },
    enabled: Boolean(user) && showBalanceTxModal,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const [showRechargeModal, setShowRechargeModal] = useState(false);
  const [rechargeAmount, setRechargeAmount] = useState("100");
  const [showPaymentGuideModal, setShowPaymentGuideModal] = useState(false);
  const [paymentGuideOrderNo, setPaymentGuideOrderNo] = useState<string | null>(
    null
  );

  const [showPaymentMethodModal, setShowPaymentMethodModal] = useState(false);
  const [paymentMethodContext, setPaymentMethodContext] = useState<
    | null
    | { kind: "vip" }
    | {
        kind: "pack";
        related_type: "ai_chat" | "document_generate";
        opt: PricingPackItem;
      }
    | { kind: "recharge"; amount: number }
  >(null);

  const rechargeMutation = useAppMutation<
    { order_no: string; pay_url?: string },
    { amount: number; payment_method: "alipay" | "ikunpay" }
  >({
    mutationFn: async ({ amount, payment_method }) => {
      const createRes = await api.post("/payment/orders", {
        order_type: "recharge",
        amount,
        title: "余额充值",
        description: "余额充值",
      });
      const orderNo = String(createRes.data?.order_no || "").trim();
      if (!orderNo) throw new Error("未获取到订单号");

      const payRes = await api.post(
        `/payment/orders/${encodeURIComponent(orderNo)}/pay`,
        {
          payment_method,
        }
      );

      return {
        order_no: orderNo,
        pay_url:
          String((payRes.data as any)?.pay_url || "").trim() || undefined,
      };
    },
    errorMessageFallback: "充值失败，请稍后重试",
  });

  const openRecharge = (amount?: number) => {
    if (typeof amount === "number" && Number.isFinite(amount) && amount > 0) {
      setRechargeAmount(String(amount));
    }
    setShowRechargeModal(true);
  };

  const openPaymentGuide = (orderNo: string | null) => {
    setPaymentGuideOrderNo(orderNo);
    setShowPaymentGuideModal(true);
  };

  const fmtMoney = (value: number | null | undefined) => {
    const n = typeof value === "number" && Number.isFinite(value) ? value : 0;
    return `¥${n.toFixed(2)}`;
  };

  const txTypeLabel = (t: string) => {
    const v = String(t || "").toLowerCase();
    if (v === "recharge") return "充值";
    if (v === "consume") return "消费";
    if (v === "refund") return "退款";
    return t || "—";
  };

  const txTotalPages = useMemo(() => {
    const total = Number(balanceTxQuery.data?.total || 0);
    return Math.max(1, Math.ceil(total / txPageSize));
  }, [balanceTxQuery.data?.total, txPageSize]);

  type PackRelatedType = "ai_chat" | "document_generate";

  const [showPackModal, setShowPackModal] = useState(false);
  const [packRelatedType, setPackRelatedType] =
    useState<PackRelatedType>("ai_chat");

  const buyPackMutation = useAppMutation<
    any,
    {
      pack_count: number;
      related_type: PackRelatedType;
      amount: number;
      payment_method: "balance" | "alipay" | "ikunpay";
    }
  >({
    mutationFn: async ({
      pack_count,
      related_type,
      amount,
      payment_method,
    }) => {
      const title =
        related_type === "document_generate"
          ? `文书生成次数包（${pack_count}次）`
          : `AI咨询次数包（${pack_count}次）`;
      const description =
        related_type === "document_generate"
          ? "文书生成次数包"
          : "AI咨询次数包";

      const createRes = await api.post("/payment/orders", {
        order_type: "ai_pack",
        amount: Number.isFinite(amount) && amount > 0 ? amount : 0.01,
        title,
        description,
        related_id: pack_count,
        related_type,
      });
      const orderNo = String(createRes.data?.order_no || "").trim();
      if (!orderNo) throw new Error("未获取到订单号");

      const payRes = await api.post(
        `/payment/orders/${encodeURIComponent(orderNo)}/pay`,
        { payment_method }
      );
      return { order_no: orderNo, ...(payRes.data || {}) };
    },
    errorMessageFallback: "购买失败，请稍后重试",
    disableErrorToast: true,
  });

  const handleBuyPack = (related_type: PackRelatedType) => {
    if (!user) return;
    if (buyVipMutation.isPending || buyPackMutation.isPending) return;

    setPackRelatedType(related_type);
    setShowPackModal(true);
  };

  const handleConfirmBuyPack = (opt: PricingPackItem) => {
    if (!user) return;
    if (buyVipMutation.isPending || buyPackMutation.isPending) return;

    setPaymentMethodContext({
      kind: "pack",
      related_type: packRelatedType,
      opt,
    });
    setShowPackModal(false);
    setShowPaymentMethodModal(true);
  };

  const [urlParams, setUrlParams] = useSearchParams();
  const didInitFromUrlRef = useRef(false);
  const lastUserIdRef = useRef<number | null>(null);

  const [formData, setFormData] = useState({
    nickname: user?.nickname || "",
    phone: user?.phone || "",
  });
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);

  // 密码修改状态
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    old_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);

  // 用户统计数据
  const [userStats, setUserStats] = useState({
    post_count: 0,
    favorite_count: 0,
    comment_count: 0,
  });
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Post[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [favoritesError, setFavoritesError] = useState<string | null>(null);

  const [myPostsPage, setMyPostsPage] = useState(1);
  const myPostsPageSize = 5;
  const [showEditPostModal, setShowEditPostModal] = useState(false);
  const [editingPostId, setEditingPostId] = useState<number | null>(null);
  const [editPostForm, setEditPostForm] = useState({
    title: "",
    content: "",
    category: "法律咨询",
  });

  const statsQueryKey = useMemo(
    () => ["user-me-stats", user?.id] as const,
    [user?.id]
  );
  const favoritesQueryKey = useMemo(
    () => ["forum-favorites", user?.id, { page: 1, page_size: 5 }] as const,
    [user?.id]
  );
  const myPostsQueryKey = useMemo(
    () =>
      [
        "forum-me-posts",
        user?.id,
        { page: myPostsPage, page_size: myPostsPageSize },
      ] as const,
    [myPostsPage, myPostsPageSize, user?.id]
  );

  const statsQuery = useQuery({
    queryKey: statsQueryKey,
    queryFn: async () => {
      const res = await api.get("/user/me/stats");
      return (res.data || {
        post_count: 0,
        favorite_count: 0,
        comment_count: 0,
      }) as {
        post_count: number;
        favorite_count: number;
        comment_count: number;
      };
    },
    enabled: !!user,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const favoritesQuery = useQuery({
    queryKey: favoritesQueryKey,
    queryFn: async () => {
      const res = await api.get("/forum/favorites", {
        params: { page: 1, page_size: 5 },
      });
      const items = res.data?.items ?? [];
      return (Array.isArray(items) ? items : []) as Post[];
    },
    enabled: !!user,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const myPostsQuery = useQuery({
    queryKey: myPostsQueryKey,
    queryFn: async () => {
      const res = await api.get("/forum/me/posts", {
        params: {
          page: myPostsPage,
          page_size: myPostsPageSize,
        },
      });
      const data = res.data || {};
      const items = data?.items ?? [];
      return {
        items: Array.isArray(items) ? (items as Post[]) : ([] as Post[]),
        total: Number(data?.total || 0),
        page: Number(data?.page || myPostsPage),
        page_size: Number(data?.page_size || myPostsPageSize),
      } as { items: Post[]; total: number; page: number; page_size: number };
    },
    enabled: !!user,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const myPosts = myPostsQuery.data?.items ?? [];
  const myPostsTotal = myPostsQuery.data?.total ?? 0;
  const myPostsTotalPages = Math.max(
    1,
    Math.ceil(myPostsTotal / myPostsPageSize)
  );
  const myPostsError = myPostsQuery.isError
    ? getApiErrorMessage(myPostsQuery.error, "我的帖子加载失败")
    : null;
  const myPostsLoading =
    (myPostsQuery.isLoading || myPostsQuery.isFetching) && myPosts.length === 0;

  const loadUserStats = useCallback(() => {
    queryClient.refetchQueries({ queryKey: statsQueryKey as any });
  }, [queryClient, statsQueryKey]);

  const loadFavorites = useCallback(() => {
    queryClient.refetchQueries({ queryKey: favoritesQueryKey as any });
  }, [queryClient, favoritesQueryKey]);

  const loadMyPosts = useCallback(() => {
    queryClient.refetchQueries({ queryKey: myPostsQueryKey as any });
  }, [myPostsQueryKey, queryClient]);

  useEffect(() => {
    setStatsLoading(statsQuery.isLoading || statsQuery.isFetching);
    if (statsQuery.isError) {
      setStatsError(getApiErrorMessage(statsQuery.error, "统计数据加载失败"));
      setUserStats({ post_count: 0, favorite_count: 0, comment_count: 0 });
      return;
    }
    setStatsError(null);
    if (statsQuery.data) {
      setUserStats(statsQuery.data);
    }
  }, [
    statsQuery.data,
    statsQuery.error,
    statsQuery.isError,
    statsQuery.isFetching,
    statsQuery.isLoading,
  ]);

  useEffect(() => {
    setFavoritesLoading(favoritesQuery.isLoading || favoritesQuery.isFetching);
    if (favoritesQuery.isError) {
      setFavoritesError(
        getApiErrorMessage(favoritesQuery.error, "收藏内容加载失败")
      );
      setFavorites([]);
      return;
    }
    setFavoritesError(null);
    setFavorites(favoritesQuery.data ?? []);
  }, [
    favoritesQuery.data,
    favoritesQuery.error,
    favoritesQuery.isError,
    favoritesQuery.isFetching,
    favoritesQuery.isLoading,
  ]);

  const toggleFavoriteMutation = useAppMutation<
    { favorited?: boolean },
    number
  >({
    mutationFn: async (postId: number) => {
      const res = await api.post(`/forum/posts/${postId}/favorite`);
      return res.data as { favorited?: boolean };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: (result, postId) => {
      if (result?.favorited === false) {
        queryClient.setQueryData<Post[]>(favoritesQueryKey as any, (old) =>
          Array.isArray(old) ? old.filter((p) => p.id !== postId) : old
        );
        queryClient.setQueryData(statsQueryKey as any, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            favorite_count: Math.max(0, Number(old.favorite_count || 0) - 1),
          };
        });
        setFavorites((prev) => prev.filter((p) => p.id !== postId));
        setUserStats((prev) => ({
          ...prev,
          favorite_count: Math.max(0, (prev.favorite_count || 0) - 1),
        }));
        toast.showToast("success", "已取消收藏", {
          durationMs: 7000,
          action: {
            label: "撤销",
            onClick: () => {
              toggleFavoriteMutation.mutate(postId);
            },
            closeOnAction: true,
          },
        });
      } else if (result?.favorited === true) {
        toast.showToast("success", "收藏成功", {
          durationMs: 7000,
          action: {
            label: "撤销",
            onClick: () => {
              toggleFavoriteMutation.mutate(postId);
            },
            closeOnAction: true,
          },
        });
        loadFavorites();
        loadUserStats();
      }
    },
  });

  const handleToggleFavorite = async (postId: number) => {
    if (toggleFavoriteMutation.isPending) return;
    toggleFavoriteMutation.mutate(postId);
  };

  const openEditPost = (post: Post) => {
    setEditingPostId(post.id);
    setEditPostForm({
      title: post.title || "",
      content: post.content || "",
      category: post.category || "法律咨询",
    });
    setShowEditPostModal(true);
  };

  const closeEditPost = () => {
    setShowEditPostModal(false);
    setEditingPostId(null);
    setEditPostForm({
      title: "",
      content: "",
      category: "法律咨询",
    });
  };

  const updateMyPostMutation = useAppMutation<
    Post,
    { id: number; title: string; content: string; category: string }
  >({
    mutationFn: async (payload) => {
      const res = await api.put(`/forum/posts/${payload.id}`, {
        title: payload.title,
        content: payload.content,
        category: payload.category,
      });
      return res.data as Post;
    },
    successMessage: "更新成功",
    errorMessageFallback: "更新失败，请稍后重试",
    onSuccess: (updated) => {
      queryClient.setQueryData(myPostsQueryKey as any, (old: any) => {
        if (!old) return old;
        const nextItems = Array.isArray(old.items)
          ? old.items.map((p: Post) => (p.id === updated.id ? updated : p))
          : old.items;
        return { ...old, items: nextItems };
      });
      closeEditPost();
    },
  });

  const deleteMyPostMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/forum/posts/${id}`);
    },
    errorMessageFallback: "删除失败，请稍后重试",
    onSuccess: (_, id) => {
      queryClient.setQueryData(myPostsQueryKey as any, (old: any) => {
        if (!old) return old;
        const nextItems = Array.isArray(old.items)
          ? old.items.filter((p: Post) => p.id !== id)
          : old.items;
        const nextTotal = Math.max(0, Number(old.total || 0) - 1);
        return { ...old, items: nextItems, total: nextTotal };
      });

      queryClient.setQueryData(statsQueryKey as any, (old: any) => {
        if (!old) return old;
        return {
          ...old,
          post_count: Math.max(0, Number(old.post_count || 0) - 1),
        };
      });
      setUserStats((prev) => ({
        ...prev,
        post_count: Math.max(0, (prev.post_count || 0) - 1),
      }));

      toast.showToast("success", "已移入回收站", {
        durationMs: 7000,
        action: {
          label: "撤销",
          onClick: () => {
            void (async () => {
              try {
                await api.post(`/forum/posts/${id}/restore`);
                await Promise.all([
                  queryClient.invalidateQueries({ queryKey: myPostsQueryKey as any }),
                  queryClient.invalidateQueries({ queryKey: favoritesQueryKey as any }),
                  queryClient.invalidateQueries({ queryKey: statsQueryKey as any }),
                ]);
                loadMyPosts();
                loadFavorites();
                loadUserStats();
                toast.success("已撤销删除");
              } catch (e) {
                toast.error(getApiErrorMessage(e, "撤销失败"));
              }
            })();
          },
          closeOnAction: true,
        },
      });

      if ((myPostsQuery.data?.items?.length ?? 0) <= 1 && myPostsPage > 1) {
        setMyPostsPage((p) => Math.max(1, p - 1));
        return;
      }
      loadMyPosts();
    },
  });

  const handleDeleteMyPost = async (id: number) => {
    if (!confirm("确定要删除这篇帖子吗？")) return;
    if (deleteMyPostMutation.isPending) return;
    deleteMyPostMutation.mutate(id);
  };

  const handleEditPostSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingPostId == null) return;
    const title = editPostForm.title.trim();
    const content = editPostForm.content.trim();
    if (!title || !content) {
      toast.error("标题和内容不能为空");
      return;
    }
    if (updateMyPostMutation.isPending) return;
    updateMyPostMutation.mutate({
      id: editingPostId,
      title,
      content,
      category: editPostForm.category,
    });
  };

  // 同步用户数据
  useEffect(() => {
    if (user) {
      setFormData({
        nickname: user.nickname || "",
        phone: user.phone || "",
      });
    }
  }, [user]);

  useEffect(() => {
    if (didInitFromUrlRef.current) return;
    const raw = Number(String(urlParams.get("postsPage") ?? "1"));
    const next = Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : 1;
    setMyPostsPage(next);

    const shouldRecharge = String(urlParams.get("recharge") ?? "")
      .trim()
      .toLowerCase();
    if (
      shouldRecharge === "1" ||
      shouldRecharge === "true" ||
      shouldRecharge === "yes"
    ) {
      const rawAmount = Number(String(urlParams.get("amount") ?? ""));
      const amount =
        Number.isFinite(rawAmount) && rawAmount > 0 ? rawAmount : undefined;
      openRecharge(amount);
      setUrlParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          p.delete("recharge");
          p.delete("amount");
          return p;
        },
        { replace: true }
      );
    }
    didInitFromUrlRef.current = true;
  }, [urlParams]);

  useEffect(() => {
    const shouldPhoneVerify = String(urlParams.get("phoneVerify") ?? "")
      .trim()
      .toLowerCase();
    if (
      !(
        shouldPhoneVerify === "1" ||
        shouldPhoneVerify === "true" ||
        shouldPhoneVerify === "yes"
      )
    ) {
      return;
    }
    if (!user) return;
    openPhoneVerify();
    setUrlParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.delete("phoneVerify");
        return p;
      },
      { replace: true }
    );
  }, [setUrlParams, urlParams, user]);

  useEffect(() => {
    const shouldEmailVerify = String(urlParams.get("emailVerify") ?? "")
      .trim()
      .toLowerCase();
    if (
      !(
        shouldEmailVerify === "1" ||
        shouldEmailVerify === "true" ||
        shouldEmailVerify === "yes"
      )
    ) {
      return;
    }
    if (!user) return;

    handleRequestEmailVerification();
    setUrlParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.delete("emailVerify");
        return p;
      },
      { replace: true }
    );
  }, [handleRequestEmailVerification, setUrlParams, urlParams, user]);

  // 手机号短信验证
  const [showPhoneVerifyModal, setShowPhoneVerifyModal] = useState(false);
  const [smsPhone, setSmsPhone] = useState("");
  const [smsCode, setSmsCode] = useState("");
  const [smsDevCode, setSmsDevCode] = useState<string | null>(null);
  const [smsCooldownSeconds, setSmsCooldownSeconds] = useState(0);

  useEffect(() => {
    if (smsCooldownSeconds <= 0) return;
    const t = window.setInterval(() => {
      setSmsCooldownSeconds((s) => Math.max(0, s - 1));
    }, 1000);
    return () => window.clearInterval(t);
  }, [smsCooldownSeconds]);

  const smsSendMutation = useAppMutation<
    { message?: string; success?: boolean; code?: string | null },
    { phone: string }
  >({
    mutationFn: async ({ phone }) => {
      const res = await api.post("/user/sms/send", {
        phone,
        scene: "bind_phone",
      });
      return res.data as {
        message?: string;
        success?: boolean;
        code?: string | null;
      };
    },
    errorMessageFallback: "发送验证码失败，请稍后重试",
  });

  const smsVerifyMutation = useAppMutation<
    any,
    { phone: string; code: string }
  >({
    mutationFn: async ({ phone, code }) => {
      const res = await api.post("/user/sms/verify", {
        phone,
        scene: "bind_phone",
        code,
      });
      return res.data;
    },
    errorMessageFallback: "验证码校验失败",
  });

  const openPhoneVerify = () => {
    if (!user) return;
    setSmsPhone(String(formData.phone || user?.phone || "").trim());
    setSmsCode("");
    setSmsDevCode(null);
    setSmsCooldownSeconds(0);
    setShowPhoneVerifyModal(true);
  };

  useEffect(() => {
    const currentUserId = typeof user?.id === "number" ? user.id : null;
    if (lastUserIdRef.current === null) {
      lastUserIdRef.current = currentUserId;
      return;
    }
    if (lastUserIdRef.current === currentUserId) return;
    lastUserIdRef.current = currentUserId;
    setMyPostsPage(1);
    setUrlParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("postsPage");
        return next;
      },
      { replace: true }
    );
  }, [setUrlParams, user?.id]);

  useEffect(() => {
    if (!didInitFromUrlRef.current) return;
    setUrlParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("recharge");
        next.delete("amount");
        next.delete("phoneVerify");
        next.delete("emailVerify");
        if (myPostsPage > 1) next.set("postsPage", String(myPostsPage));
        else next.delete("postsPage");
        return next;
      },
      { replace: true }
    );
  }, [myPostsPage, setUrlParams]);

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024) {
        toast.error("图片大小不能超过2MB");
        return;
      }

      // 预览
      const reader = new FileReader();
      reader.onload = (e) => {
        setAvatarPreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);

      // 上传头像
      uploadAvatarMutation.mutate(file);
    }
  };

  const uploadAvatarMutation = useAppMutation<void, File>({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post("/upload/avatar", fd, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      const url = res.data?.url;
      await api.put("/user/me", { avatar: url });
    },
    successMessage: "头像上传成功",
    errorMessageFallback: "头像上传失败",
    onError: () => {
      setAvatarPreview(null);
    },
  });

  const updateProfileMutation = useAppMutation<void, typeof formData>({
    mutationFn: async (payload) => {
      await api.put("/user/me", { nickname: payload.nickname });
    },
    successMessage: "个人信息更新成功",
    errorMessageFallback: "更新失败，请稍后重试",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (updateProfileMutation.isPending) return;
    updateProfileMutation.mutate(formData);
  };

  const changePasswordMutation = useAppMutation<
    void,
    { old_password: string; new_password: string }
  >({
    mutationFn: async (payload) => {
      await api.put("/user/me/password", payload);
    },
    successMessage: "密码修改成功",
    errorMessageFallback: "密码修改失败，请稍后重试",
    disableErrorToast: true,
    onSuccess: () => {
      setShowPasswordModal(false);
      setPasswordForm({
        old_password: "",
        new_password: "",
        confirm_password: "",
      });
    },
    onError: (err) => {
      const status = (err as any)?.response?.status;
      if (status === 403) {
        const detail = String((err as any)?.response?.data?.detail || "");
        if (detail.includes("手机号")) {
          toast.warning("请先完成手机号验证");
          setUrlParams(
            (prev) => {
              const p = new URLSearchParams(prev);
              p.set("phoneVerify", "1");
              return p;
            },
            { replace: true }
          );
          return;
        }
        if (detail.includes("邮箱")) {
          toast.warning("请先完成邮箱验证");
          setUrlParams(
            (prev) => {
              const p = new URLSearchParams(prev);
              p.set("emailVerify", "1");
              return p;
            },
            { replace: true }
          );
          return;
        }
      }
      toast.error(getApiErrorMessage(err, "密码修改失败，请稍后重试"));
    },
  });

  // 密码修改处理
  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!user) return;

    if (!user.phone_verified) {
      toast.warning("请先完成手机号验证");
      setUrlParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          p.set("phoneVerify", "1");
          return p;
        },
        { replace: true }
      );
      return;
    }
    if (!user.email_verified) {
      toast.warning("请先完成邮箱验证");
      setUrlParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          p.set("emailVerify", "1");
          return p;
        },
        { replace: true }
      );
      return;
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error("两次输入的新密码不一致");
      return;
    }

    if (passwordForm.new_password.length < 6) {
      toast.error("新密码长度至少6位");
      return;
    }

    if (changePasswordMutation.isPending) return;
    changePasswordMutation.mutate({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    });
  };

  const stats = [
    {
      icon: MessageSquare,
      label: "发布帖子",
      value: userStats.post_count,
      color: "text-blue-600 dark:text-blue-400",
    },
    {
      icon: Heart,
      label: "收藏内容",
      value: userStats.favorite_count,
      color: "text-pink-600 dark:text-pink-400",
    },
    {
      icon: Clock,
      label: "评论数",
      value: userStats.comment_count,
      color: "text-emerald-600 dark:text-green-400",
    },
  ];

  const postCategories = [
    "法律咨询",
    "经验分享",
    "案例讨论",
    "政策解读",
    "其他",
  ];

  // 格式化日期
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card variant="surface" padding="lg" className="text-center max-w-md">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-amber-500/20 to-orange-500/10 flex items-center justify-center">
            <Shield className="h-10 w-10 text-amber-600 dark:text-amber-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900 mb-2 dark:text-white">
            请先登录
          </h2>
          <p className="text-slate-600 dark:text-white/50">
            登录后即可查看和编辑个人信息
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="个人设置"
        title="个人中心"
        description="管理您的账户信息和偏好设置"
        tone={actualTheme}
      />

      <div className="grid lg:grid-cols-3 gap-6">
        {/* 左侧：用户资料卡片 */}
        <div className="lg:col-span-1 space-y-6">
          {/* 头像和基本信息 */}
          <Card variant="surface" padding="lg">
            <div className="text-center">
              {/* 头像区域 - 美化 */}
              <div className="relative inline-block mb-6">
                <div className="absolute -inset-1 bg-gradient-to-br from-amber-400 to-orange-500 rounded-full opacity-20 blur-lg"></div>
                <div
                  onClick={handleAvatarClick}
                  className="relative w-32 h-32 rounded-full bg-gradient-to-br from-amber-500/30 to-orange-500/20 flex items-center justify-center cursor-pointer group overflow-hidden border-4 border-slate-200/70 hover:border-amber-500/40 transition-all duration-300 dark:border-white/10 dark:hover:border-amber-400/30"
                >
                  {avatarPreview || user.avatar ? (
                    <FadeInImage
                      src={avatarPreview || user.avatar}
                      alt="头像"
                      wrapperClassName="w-full h-full"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex flex-col items-center">
                      <User className="h-14 w-14 text-amber-400" />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-slate-900/60 opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col items-center justify-center dark:bg-black/60">
                    <Camera className="h-7 w-7 text-white mb-1" />
                    <span className="text-white text-xs">更换头像</span>
                  </div>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarChange}
                  className="hidden"
                />
              </div>

              {/* 用户名和昵称 */}
              <h3 className="text-2xl font-bold text-slate-900 mb-1 dark:text-white">
                {user.nickname || user.username}
              </h3>
              <p className="text-slate-600 text-sm mb-4 dark:text-white/50">
                @{user.username}
              </p>

              {/* 角色标签 */}
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
                <Shield className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                <span className="text-amber-700 text-sm font-medium dark:text-amber-400">
                  {user.role === "admin"
                    ? "管理员"
                    : user.role === "lawyer"
                      ? "认证律师"
                      : "普通用户"}
                </span>
              </div>

              {/* 注册时间 */}
              {user.created_at && (
                <div className="flex items-center justify-center gap-2 mt-4 text-slate-500 text-sm dark:text-white/40">
                  <Calendar className="h-4 w-4" />
                  <span>加入于 {formatDate(user.created_at)}</span>
                </div>
              )}
            </div>

            {/* 统计数据 - 美化 */}
            <div className="grid grid-cols-3 gap-4 mt-8 pt-6 border-t border-slate-200/70 dark:border-white/5">
              {statsLoading ? (
                Array.from({ length: 3 }).map((_, idx) => (
                  <div key={idx} className="text-center">
                    <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-slate-900/5 flex items-center justify-center dark:bg-white/5">
                      <Skeleton width="20px" height="20px" />
                    </div>
                    <div className="flex justify-center">
                      <Skeleton width="56px" height="20px" />
                    </div>
                    <div className="mt-2 flex justify-center">
                      <Skeleton width="64px" height="12px" />
                    </div>
                  </div>
                ))
              ) : statsError ? (
                <div className="col-span-3 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                  <div>{statsError}</div>
                  <Button variant="outline" onClick={loadUserStats}>
                    重试
                  </Button>
                </div>
              ) : (
                stats.map(({ icon: Icon, label, value, color }) => (
                  <div key={label} className="text-center group cursor-pointer">
                    <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-slate-900/5 flex items-center justify-center group-hover:bg-slate-900/10 transition-colors dark:bg-white/5 dark:group-hover:bg-white/10">
                      <Icon className={`h-5 w-5 ${color}`} />
                    </div>
                    <p className="text-xl font-bold text-slate-900 dark:text-white">
                      {value}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-white/40">
                      {label}
                    </p>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card variant="surface" padding="md">
            <div className="flex items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-2">
                <Wallet className="h-4 w-4 text-slate-400 dark:text-white/40" />
                <h4 className="text-sm font-medium text-slate-600 dark:text-white/60">
                  我的资产
                </h4>
              </div>
              <Button
                variant="outline"
                size="sm"
                icon={RefreshCw}
                isLoading={balanceQuery.isFetching}
                loadingText="刷新中..."
                onClick={() => balanceQuery.refetch()}
                disabled={balanceQuery.isFetching}
              >
                刷新
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
                <div className="text-xs text-slate-500 dark:text-white/45">
                  余额
                </div>
                <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                  {fmtMoney(balanceQuery.data?.balance)}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
                <div className="text-xs text-slate-500 dark:text-white/45">
                  冻结
                </div>
                <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                  {fmtMoney(balanceQuery.data?.frozen)}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
                <div className="text-xs text-slate-500 dark:text-white/45">
                  累计充值
                </div>
                <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                  {fmtMoney(balanceQuery.data?.total_recharged)}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
                <div className="text-xs text-slate-500 dark:text-white/45">
                  累计消费
                </div>
                <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                  {fmtMoney(balanceQuery.data?.total_consumed)}
                </div>
              </div>
            </div>

            {balanceQuery.isError ? (
              <div className="mt-3 flex items-start justify-between gap-3">
                <div className="text-xs text-red-500 dark:text-red-300">
                  {getApiErrorMessage(balanceQuery.error, "余额加载失败")}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  icon={RefreshCw}
                  isLoading={balanceQuery.isFetching}
                  loadingText="重试中..."
                  onClick={() => void balanceQuery.refetch()}
                  disabled={balanceQuery.isFetching}
                >
                  重试
                </Button>
              </div>
            ) : null}

            <div className="mt-4 flex items-center gap-2">
              <Button
                icon={CreditCard}
                onClick={() => {
                  setRechargeAmount("100");
                  setShowRechargeModal(true);
                }}
                disabled={rechargeMutation.isPending}
              >
                充值
              </Button>
              <Button
                variant="outline"
                icon={FileText}
                onClick={() => {
                  setTxPage(1);
                  setShowBalanceTxModal(true);
                }}
                disabled={rechargeMutation.isPending}
              >
                明细
              </Button>
            </div>
          </Card>

          <Card variant="surface" padding="md">
            <h4 className="text-sm font-medium text-slate-600 mb-4 dark:text-white/60">
              账户状态
            </h4>

            <div className="mb-4 rounded-xl border border-slate-200/70 bg-slate-900/5 px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-semibold text-slate-600 dark:text-white/60">
                  今日配额
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  icon={RefreshCw}
                  isLoading={quotasQuery.isFetching}
                  loadingText="刷新中..."
                  onClick={() => quotasQuery.refetch()}
                  disabled={quotasQuery.isFetching}
                >
                  刷新配额
                </Button>
              </div>

              <div className="mt-2 space-y-2 text-xs text-slate-600 dark:text-white/60">
                <div className="flex items-center justify-between gap-2">
                  <span>AI 咨询</span>
                  <span className="font-medium text-slate-800 dark:text-white">
                    {quotasQuery.data
                      ? `${Number(
                        quotasQuery.data.ai_chat_remaining || 0
                      )}/${Number(
                        quotasQuery.data.ai_chat_limit || 0
                      )} · 次数包 ${Number(
                        quotasQuery.data.ai_chat_pack_remaining || 0
                      )}`
                      : "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span>文书生成</span>
                  <span className="font-medium text-slate-800 dark:text-white">
                    {quotasQuery.data
                      ? `${Number(
                        quotasQuery.data.document_generate_remaining || 0
                      )}/${Number(
                        quotasQuery.data.document_generate_limit || 0
                      )} · 次数包 ${Number(
                        quotasQuery.data.document_generate_pack_remaining || 0
                      )}`
                      : "—"}
                  </span>
                </div>
              </div>

              {quotasQuery.isError ? (
                <div className="mt-3 flex items-start justify-between gap-3">
                  <div className="text-xs text-red-500 dark:text-red-300">
                    {getApiErrorMessage(quotasQuery.error, "配额加载失败")}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={RefreshCw}
                    isLoading={quotasQuery.isFetching}
                    loadingText="重试中..."
                    onClick={() => void quotasQuery.refetch()}
                    disabled={quotasQuery.isFetching}
                  >
                    重试
                  </Button>
                </div>
              ) : null}
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    邮箱验证
                  </span>
                </div>
                {isEmailVerified ? (
                  <div className="flex items-center gap-1 text-green-400">
                    <CheckCircle className="h-4 w-4" />
                    <span className="text-xs">已验证</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                      <AlertCircle className="h-4 w-4" />
                      <span className="text-xs">未验证</span>
                    </div>
                    <button
                      type="button"
                      onClick={handleRequestEmailVerification}
                      disabled={
                        requestEmailVerificationMutation.isPending ||
                        buyVipMutation.isPending ||
                        buyPackMutation.isPending
                      }
                      className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300 disabled:opacity-50"
                    >
                      {requestEmailVerificationMutation.isPending
                        ? "发送中..."
                        : "去验证"}
                      {requestEmailVerificationMutation.isPending ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <ExternalLink className="h-3 w-3" />
                      )}
                    </button>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    手机绑定
                  </span>
                </div>
                {isPhoneVerified ? (
                  <div className="flex items-center gap-1 text-green-400">
                    <CheckCircle className="h-4 w-4" />
                    <span className="text-xs">已验证</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                      <AlertCircle className="h-4 w-4" />
                      <span className="text-xs">
                        {user.phone ? "待验证" : "未绑定"}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={openPhoneVerify}
                      disabled={
                        smsSendMutation.isPending ||
                        smsVerifyMutation.isPending ||
                        buyVipMutation.isPending ||
                        buyPackMutation.isPending
                      }
                      className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300 disabled:opacity-50"
                    >
                      去验证
                      <ExternalLink className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    账户安全
                  </span>
                </div>
                <div className="flex items-center gap-1 text-green-400">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-xs">正常</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    律师预约
                  </span>
                </div>
                <Link
                  to="/orders?tab=consultations"
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
                >
                  查看
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    律师认证
                  </span>
                </div>
                <Link
                  to="/lawyer/verification"
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
                >
                  查看
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>

              {String(user.role || "").toLowerCase() === "lawyer" ? (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-slate-400 dark:text-white/40" />
                    <span className="text-sm text-slate-700 dark:text-white/70">
                      律师工作台
                    </span>
                  </div>
                  <Link
                    to="/lawyer"
                    className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
                  >
                    进入
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              ) : null}

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Crown
                    className={`h-4 w-4 ${
                      isVipActive
                        ? "text-amber-500"
                        : "text-slate-400 dark:text-white/40"
                    }`}
                  />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    VIP会员
                  </span>
                  <span
                    className={`text-[11px] px-2 py-0.5 rounded-full border ${
                      isVipActive
                        ? "bg-amber-500/10 text-amber-700 border-amber-500/20 dark:text-amber-300"
                        : "bg-slate-900/5 text-slate-600 border-slate-200/70 dark:bg-white/5 dark:text-white/55 dark:border-white/10"
                    }`}
                  >
                    VIP
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs ${isVipActive
                      ? "text-green-500"
                      : "text-slate-500 dark:text-white/50"
                      }`}
                  >
                    {isVipActive
                      ? `有效期至 ${vipExpiresAt ? vipExpiresAt.toLocaleDateString() : ""
                      }`
                      : "未开通"}
                  </span>
                  <button
                    type="button"
                    onClick={handleBuyVip}
                    disabled={
                      buyVipMutation.isPending || buyPackMutation.isPending
                    }
                    className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300 disabled:opacity-50"
                  >
                    {buyVipMutation.isPending
                      ? "处理中..."
                      : isVipActive
                        ? "续费"
                        : "开通"}
                    {buyVipMutation.isPending ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <ExternalLink className="h-3 w-3" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    AI咨询次数包
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleBuyPack("ai_chat")}
                  disabled={
                    buyVipMutation.isPending || buyPackMutation.isPending
                  }
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300 disabled:opacity-50"
                >
                  {buyPackMutation.isPending ? "处理中..." : "购买"}
                  {buyPackMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <ExternalLink className="h-3 w-3" />
                  )}
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    文书生成次数包
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleBuyPack("document_generate")}
                  disabled={
                    buyVipMutation.isPending || buyPackMutation.isPending
                  }
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300 disabled:opacity-50"
                >
                  {buyPackMutation.isPending ? "处理中..." : "购买"}
                  {buyPackMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <ExternalLink className="h-3 w-3" />
                  )}
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    我的订单
                  </span>
                </div>
                <Link
                  to="/orders?tab=payment"
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
                >
                  查看
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    客服反馈
                  </span>
                </div>
                <Link
                  to="/feedback"
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
                >
                  查看
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">
                    通知中心
                  </span>
                </div>
                <Link
                  to="/notifications"
                  className="text-amber-600 text-xs hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
                >
                  查看
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </Card>
        </div>

        {/* 右侧：编辑表单 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 基本信息表单 */}
          <Card variant="surface" padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <User className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  基本信息
                </h3>
                <p className="text-sm text-slate-600 dark:text-white/50">
                  更新您的个人资料信息
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid sm:grid-cols-2 gap-6">
                <Input
                  label="用户名"
                  icon={User}
                  value={user.username}
                  disabled
                  className="py-3"
                />
                <Input
                  label="邮箱"
                  icon={Mail}
                  value={user.email}
                  disabled
                  className="py-3"
                />
              </div>

              <div className="grid sm:grid-cols-2 gap-6">
                <Input
                  label="昵称"
                  icon={User}
                  value={formData.nickname}
                  onChange={(e) =>
                    setFormData({ ...formData, nickname: e.target.value })
                  }
                  placeholder="设置您的昵称"
                  className="py-3"
                  disabled={updateProfileMutation.isPending}
                />
                <Input
                  label="手机号"
                  icon={Phone}
                  value={formData.phone}
                  readOnly
                  placeholder="绑定手机号"
                  className="py-3"
                  disabled={updateProfileMutation.isPending}
                />
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  icon={Save}
                  isLoading={updateProfileMutation.isPending}
                  loadingText="保存中..."
                  className="px-8"
                  disabled={updateProfileMutation.isPending}
                >
                  保存修改
                </Button>
              </div>
            </form>
          </Card>

          {/* 安全设置 */}
          <Card variant="surface" padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Lock className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  安全设置
                </h3>
                <p className="text-sm text-slate-600 dark:text-white/50">
                  管理您的账户安全选项
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/[0.02] dark:border-white/5">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-slate-900 font-medium dark:text-white">
                    登录密码
                  </h4>
                  <p className="text-sm text-slate-600 mt-1 dark:text-white/50">
                    定期更换密码可以提高账户安全性
                  </p>
                </div>
                <Button
                  variant="secondary"
                  icon={Lock}
                  onClick={() => {
                    if (!isEmailVerified) {
                      toast.warning("请先完成邮箱验证");
                      setUrlParams(
                        (prev) => {
                          const p = new URLSearchParams(prev);
                          p.set("emailVerify", "1");
                          return p;
                        },
                        { replace: true }
                      );
                      return;
                    }
                    setShowPasswordModal(true);
                  }}
                >
                  修改密码
                </Button>
              </div>
            </div>
          </Card>

          <Card variant="surface" padding="lg">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-slate-900/5 flex items-center justify-center dark:bg-white/5">
                  <FileText className="h-5 w-5 text-slate-600 dark:text-white/60" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    我的帖子
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-white/50">
                    管理您发布的帖子内容
                  </p>
                </div>
              </div>
              <Link
                to="/forum/new"
                className="text-amber-600 text-sm hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
              >
                去发布
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>

            {myPostsLoading ? (
              <ListSkeleton count={3} />
            ) : myPostsError ? (
              <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                <div>{myPostsError}</div>
                <Button variant="outline" onClick={loadMyPosts}>
                  重试
                </Button>
              </div>
            ) : myPosts.length > 0 ? (
              <div className="space-y-3">
                {myPosts.map((post) => (
                  <div
                    key={post.id}
                    className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/[0.02] dark:border-white/5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <Link to={`/forum/post/${post.id}`} className="block">
                          <h4 className="text-slate-900 font-medium line-clamp-1 mb-2 dark:text-white hover:text-amber-600 dark:hover:text-amber-400 transition-colors">
                            {post.title}
                          </h4>
                        </Link>
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          {post.review_status === "pending" ? (
                            <Badge
                              variant="warning"
                              size="sm"
                              title={post.review_reason || undefined}
                            >
                              审核中
                            </Badge>
                          ) : post.review_status === "rejected" ? (
                            <Badge
                              variant="danger"
                              size="sm"
                              title={post.review_reason || undefined}
                            >
                              已驳回
                            </Badge>
                          ) : (
                            <Badge variant="success" size="sm">
                              已通过
                            </Badge>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-white/40">
                          <span>{post.category}</span>
                          <span>
                            {new Date(post.created_at).toLocaleDateString()}
                          </span>
                          <span className="flex items-center gap-1">
                            <Heart className="h-3 w-3" />
                            {post.like_count}
                          </span>
                          <span className="flex items-center gap-1">
                            <MessageSquare className="h-3 w-3" />
                            {post.comment_count}
                          </span>
                        </div>
                      </div>

                      <div className="shrink-0 flex items-center gap-2">
                        <Link to={`/forum/post/${post.id}`}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-2"
                            title="查看"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2"
                          title="编辑"
                          onClick={() => openEditPost(post)}
                          disabled={
                            updateMyPostMutation.isPending ||
                            deleteMyPostMutation.isPending
                          }
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2 text-red-500 hover:text-red-600 dark:text-red-300 dark:hover:text-red-200"
                          title="删除"
                          onClick={() => handleDeleteMyPost(post.id)}
                          disabled={
                            deleteMyPostMutation.isPending ||
                            updateMyPostMutation.isPending
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}

                <Pagination
                  currentPage={myPostsPage}
                  totalPages={myPostsTotalPages}
                  onPageChange={(p) => setMyPostsPage(p)}
                  className="pt-2"
                />
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title="暂无发布帖子"
                description="去论坛发布你的第一篇帖子"
                tone={actualTheme}
                action={
                  <Link to="/forum/new">
                    <Button variant="outline">去发布</Button>
                  </Link>
                }
              />
            )}
          </Card>

          {/* 收藏内容区域 */}
          <Card variant="surface" padding="lg">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-pink-500/10 flex items-center justify-center">
                  <Heart className="h-5 w-5 text-pink-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    我的收藏
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-white/50">
                    您收藏的文章和帖子
                  </p>
                </div>
              </div>
              <Link
                to={`/forum?cat=${encodeURIComponent("我的收藏")}`}
                className="text-amber-600 text-sm hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
              >
                查看全部
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>

            {favoritesLoading ? (
              <ListSkeleton count={3} />
            ) : favoritesError ? (
              <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                <div>{favoritesError}</div>
                <Button variant="outline" onClick={loadFavorites}>
                  重试
                </Button>
              </div>
            ) : favorites.length > 0 ? (
              <div className="space-y-3">
                {favorites.map((post) => (
                  <Link
                    key={post.id}
                    to={`/forum/post/${post.id}`}
                    className="block p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 hover:bg-slate-50 hover:border-slate-200 transition-all dark:bg-white/[0.02] dark:border-white/5 dark:hover:bg-white/[0.05] dark:hover:border-white/10"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h4 className="text-slate-900 font-medium line-clamp-1 mb-2 dark:text-white">
                          {post.title}
                        </h4>
                        <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-white/40">
                          <span className="flex items-center gap-1">
                            <Heart className="h-3 w-3" />
                            {post.like_count}
                          </span>
                          <span className="flex items-center gap-1">
                            <MessageSquare className="h-3 w-3" />
                            {post.comment_count}
                          </span>
                          <span className="flex items-center gap-1">
                            <Star className="h-3 w-3" />
                            {post.favorite_count ?? 0}
                          </span>
                          <span>{post.category}</span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleToggleFavorite(post.id);
                        }}
                        className="shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors dark:border-white/10 dark:bg-white/5 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white"
                        aria-label="取消收藏"
                        title="取消收藏"
                      >
                        <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                        <span className="text-xs">取消</span>
                      </button>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Heart}
                title="暂无收藏内容"
                description="浏览帖子时可以点击收藏"
                tone={actualTheme}
                action={
                  <Link to="/forum">
                    <Button variant="outline">去逛逛论坛</Button>
                  </Link>
                }
              />
            )}
          </Card>
        </div>
      </div>

      <Modal
        isOpen={showBalanceTxModal}
        onClose={() => {
          if (balanceTxQuery.isFetching) return;
          setShowBalanceTxModal(false);
        }}
        title="余额明细"
        description="查看充值/消费/退款记录"
        size="lg"
      >
        <div className="space-y-4">
          {balanceTxQuery.isLoading && !balanceTxQuery.data ? (
            <ListSkeleton count={5} />
          ) : balanceTxQuery.isError ? (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
              <div>
                {getApiErrorMessage(
                  balanceTxQuery.error,
                  "加载失败，请稍后重试"
                )}
              </div>
              <Button
                variant="outline"
                onClick={() => balanceTxQuery.refetch()}
              >
                重试
              </Button>
            </div>
          ) : (balanceTxQuery.data?.items ?? []).length > 0 ? (
            <div className="space-y-3">
              {(balanceTxQuery.data?.items ?? []).map((t) => {
                const amount = Number(t.amount || 0);
                const positive = amount > 0;
                const color = positive
                  ? "text-emerald-600 dark:text-emerald-400"
                  : amount < 0
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-slate-600 dark:text-white/60";
                return (
                  <div
                    key={t.id}
                    className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Badge variant="default">{txTypeLabel(t.type)}</Badge>
                          <div className="text-sm font-medium text-slate-900 dark:text-white line-clamp-1">
                            {t.description || "—"}
                          </div>
                        </div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-white/45">
                          {t.created_at
                            ? new Date(t.created_at).toLocaleString()
                            : ""}
                          {t.balance_after != null
                            ? ` · 余额 ${fmtMoney(
                              Number(t.balance_after || 0)
                            )}`
                            : ""}
                        </div>
                      </div>
                      <div
                        className={`shrink-0 text-sm font-semibold ${color}`}
                      >
                        {positive ? "+" : ""}
                        {fmtMoney(amount)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              icon={Wallet}
              title="暂无明细"
              description="你的充值/消费记录会在这里显示"
              tone={actualTheme}
              size="md"
            />
          )}

          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-slate-500 dark:text-white/45">
              共 {Number(balanceTxQuery.data?.total || 0)} 条
            </div>
            <Pagination
              currentPage={txPage}
              totalPages={txTotalPages}
              onPageChange={(p) => setTxPage(p)}
            />
          </div>
        </div>
      </Modal>

      <PaymentMethodModal
        isOpen={showPaymentMethodModal}
        onClose={() => {
          if (
            buyVipMutation.isPending ||
            buyPackMutation.isPending ||
            rechargeMutation.isPending
          )
            return;
          setShowPaymentMethodModal(false);
        }}
        onBack={(() => {
          const ctx = paymentMethodContext;
          if (!ctx) return undefined;
          if (ctx.kind === "pack") {
            return () => {
              if (buyPackMutation.isPending) return;
              setShowPaymentMethodModal(false);
              setShowPackModal(true);
            };
          }
          if (ctx.kind === "recharge") {
            return () => {
              if (rechargeMutation.isPending) return;
              setShowPaymentMethodModal(false);
              setShowRechargeModal(true);
            };
          }
          return undefined;
        })()}
        backLabel="返回修改"
        title={
          paymentMethodContext?.kind === "vip"
            ? "选择支付方式"
            : paymentMethodContext?.kind === "pack"
              ? "选择支付方式"
              : "选择支付方式"
        }
        description={
          paymentMethodContext?.kind === "vip"
            ? `开通/续费 VIP（${vipDays}天 ¥${vipPrice.toFixed(2)}）`
            : paymentMethodContext?.kind === "pack"
              ? `购买次数包（${paymentMethodContext.opt.count}次 ¥${Number(
                  paymentMethodContext.opt.price || 0
                ).toFixed(2)}）`
              : paymentMethodContext?.kind === "recharge"
                ? `充值 ¥${Number(paymentMethodContext.amount || 0).toFixed(2)}`
                : undefined
        }
        busy={
          buyVipMutation.isPending ||
          buyPackMutation.isPending ||
          rechargeMutation.isPending
        }
        options={(() => {
          const loadingChannels = !channelStatusQuery.data && channelStatusQuery.isLoading;
          const canAlipay = channelStatusQuery.data?.alipay_configured === true;
          const canIkunpay = channelStatusQuery.data?.ikunpay_configured === true;
          const thirdPartyDisabledReason = loadingChannels
            ? "加载中"
            : "未配置";

          if (paymentMethodContext?.kind === "recharge") {
            return [
              {
                method: "alipay" as PaymentMethod,
                label: "支付宝",
                description: "跳转到支付宝完成支付",
                enabled: canAlipay,
                disabledReason: thirdPartyDisabledReason,
              },
              {
                method: "ikunpay" as PaymentMethod,
                label: "爱坤支付",
                description: "跳转到爱坤支付完成支付",
                enabled: canIkunpay,
                disabledReason: thirdPartyDisabledReason,
              },
            ];
          }

          return [
            {
              method: "balance" as PaymentMethod,
              label: "余额支付",
              description: "即时生效",
              enabled: true,
            },
            {
              method: "alipay" as PaymentMethod,
              label: "支付宝",
              description: "跳转到支付宝完成支付",
              enabled: canAlipay,
              disabledReason: thirdPartyDisabledReason,
            },
            {
              method: "ikunpay" as PaymentMethod,
              label: "爱坤支付",
              description: "跳转到爱坤支付完成支付",
              enabled: canIkunpay,
              disabledReason: thirdPartyDisabledReason,
            },
          ];
        })()}
        onSelect={(method) => {
          const ctx = paymentMethodContext;
          setShowPaymentMethodModal(false);

          if (!ctx) return;

          if (ctx.kind === "vip") {
            buyVipMutation.mutate(
              { payment_method: method as any },
              {
                onSuccess: async (data) => {
                  if (method !== "balance") {
                    const url = String((data as any)?.pay_url || "").trim();
                    if (url) {
                      window.open(url, "_blank", "noopener,noreferrer");
                      toast.success("已打开支付页面");
                      openPaymentGuide(String((data as any)?.order_no || null));
                    } else {
                      toast.error("未获取到支付链接");
                    }
                    return;
                  }

                  toast.success("开通成功");
                  queryClient.invalidateQueries({ queryKey: ["user-me"] as any });
                  queryClient.invalidateQueries({
                    queryKey: queryKeys.userMeQuotas() as any,
                  });
                },
                onError: (err) => {
                  const msg = getApiErrorMessage(err, "开通失败");
                  if (String(msg).includes("余额不足")) {
                    toast.warning("余额不足，请先充值");
                    openRecharge(vipPrice);
                    return;
                  }
                  toast.error(msg);
                },
              }
            );
            return;
          }

          if (ctx.kind === "pack") {
            buyPackMutation.mutate(
              {
                pack_count: ctx.opt.count,
                related_type: ctx.related_type as any,
                amount: Number(ctx.opt.price || 0),
                payment_method: method as any,
              },
              {
                onSuccess: async (data) => {
                  if (method !== "balance") {
                    const url = String((data as any)?.pay_url || "").trim();
                    if (url) {
                      window.open(url, "_blank", "noopener,noreferrer");
                      toast.success("已打开支付页面");
                      setShowPackModal(false);
                      openPaymentGuide(String((data as any)?.order_no || null));
                    } else {
                      toast.error("未获取到支付链接");
                    }
                    return;
                  }

                  toast.success("购买成功");
                  setShowPackModal(false);
                  queryClient.invalidateQueries({ queryKey: ["user-me"] as any });
                  queryClient.invalidateQueries({
                    queryKey: queryKeys.userMeQuotas() as any,
                  });
                },
                onError: (err) => {
                  const msg = getApiErrorMessage(err, "购买失败");
                  if (String(msg).includes("余额不足")) {
                    toast.warning("余额不足，请先充值");
                    openRecharge(Number(ctx.opt.price || 0));
                    return;
                  }
                  toast.error(msg);
                },
              }
            );
            return;
          }

          if (ctx.kind === "recharge") {
            if (method === "balance") {
              toast.error("充值不支持余额支付");
              return;
            }

            rechargeMutation.mutate(
              { amount: ctx.amount, payment_method: method as any },
              {
                onSuccess: (data) => {
                  const payUrl = String((data as any)?.pay_url || "").trim();
                  if (payUrl) {
                    window.open(payUrl, "_blank", "noopener,noreferrer");
                    toast.success("已打开支付页面");
                    openPaymentGuide(String((data as any)?.order_no || null));
                    setShowRechargeModal(false);
                    return;
                  }
                  toast.success("订单已创建，请前往订单页继续支付");
                  setShowRechargeModal(false);
                },
                onError: (err) => {
                  toast.error(getApiErrorMessage(err, "充值失败"));
                },
              }
            );
          }
        }}
      />

      <Modal
        isOpen={showRechargeModal}
        onClose={() => {
          if (rechargeMutation.isPending) return;
          setShowRechargeModal(false);
        }}
        title="余额充值"
        description="选择充值金额并跳转支付"
        size="sm"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[50, 100, 200, 500, 1000, 2000].map((amt) => (
              <Button
                key={amt}
                type="button"
                variant={
                  String(amt) === String(rechargeAmount).trim()
                    ? "primary"
                    : "outline"
                }
                disabled={rechargeMutation.isPending}
                onClick={() => setRechargeAmount(String(amt))}
              >
                ¥{amt}
              </Button>
            ))}
          </div>

          <Input
            label="自定义金额（元）"
            value={rechargeAmount}
            onChange={(e) => setRechargeAmount(e.target.value)}
            disabled={rechargeMutation.isPending}
            placeholder="例如：100"
          />

          <Button
            type="button"
            fullWidth
            isLoading={rechargeMutation.isPending}
            loadingText="创建订单中..."
            disabled={rechargeMutation.isPending}
            onClick={() => {
              const amt = Number(String(rechargeAmount || "").trim());
              if (!Number.isFinite(amt) || amt <= 0) {
                toast.error("请输入正确的充值金额");
                return;
              }

              setPaymentMethodContext({ kind: "recharge", amount: amt });
              setShowRechargeModal(false);
              setShowPaymentMethodModal(true);
            }}
          >
            去支付
          </Button>

          <Button
            type="button"
            variant="secondary"
            fullWidth
            onClick={() => setShowRechargeModal(false)}
            disabled={rechargeMutation.isPending}
          >
            取消
          </Button>
        </div>
      </Modal>

      <Modal
        isOpen={showPaymentGuideModal}
        onClose={() => setShowPaymentGuideModal(false)}
        title="支付提示"
        description="支付完成后请返回本站刷新状态"
        size="sm"
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/70 bg-slate-900/5 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/70">
            <div>1) 在新打开的支付页面完成支付</div>
            <div className="mt-1">2) 回到本页点击“我已支付，刷新余额/权益”</div>
          </div>

          <Button
            fullWidth
            icon={RefreshCw}
            onClick={async () => {
              setShowPaymentGuideModal(false);
              await refreshUser();
              await balanceQuery.refetch();
              await quotasQuery.refetch();
              toast.success("已刷新账户状态");
            }}
          >
            我已支付，刷新余额/权益
          </Button>

          {paymentGuideOrderNo ? (
            <Link
              to={`/payment/return?order_no=${encodeURIComponent(
                paymentGuideOrderNo
              )}`}
              className="block"
            >
              <Button variant="outline" fullWidth icon={ExternalLink}>
                去支付结果页查看状态
              </Button>
            </Link>
          ) : null}

          <Link to="/orders?tab=payment" className="block">
            <Button variant="outline" fullWidth icon={ExternalLink}>
              去订单页查看/刷新
            </Button>
          </Link>

          {paymentGuideOrderNo ? (
            <div className="text-xs text-slate-500 dark:text-white/45">
              订单号：{paymentGuideOrderNo}
            </div>
          ) : null}
        </div>
      </Modal>

      <Modal
        isOpen={showPhoneVerifyModal}
        onClose={() => {
          if (smsSendMutation.isPending || smsVerifyMutation.isPending) return;
          setShowPhoneVerifyModal(false);
        }}
        title="手机号验证"
        description="发送验证码并完成绑定"
        size="sm"
      >
        <div className="space-y-4">
          <Input
            label="手机号"
            icon={Phone}
            value={smsPhone}
            onChange={(e) => setSmsPhone(e.target.value)}
            placeholder="请输入手机号"
            disabled={smsSendMutation.isPending || smsVerifyMutation.isPending}
          />

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={
                smsSendMutation.isPending ||
                smsVerifyMutation.isPending ||
                smsCooldownSeconds > 0 ||
                !String(smsPhone || "").trim()
              }
              onClick={() => {
                const phone = String(smsPhone || "").trim();
                if (!phone) {
                  toast.error("请输入手机号");
                  return;
                }
                smsSendMutation.mutate(
                  { phone },
                  {
                    onSuccess: (data) => {
                      const devCode = String((data as any)?.code || "").trim();
                      setSmsDevCode(devCode ? devCode : null);
                      setSmsCooldownSeconds(60);
                      toast.success("验证码已发送");
                    },
                  }
                );
              }}
            >
              {smsCooldownSeconds > 0
                ? `重新发送(${smsCooldownSeconds}s)`
                : "发送验证码"}
            </Button>

            {smsDevCode ? (
              <div className="text-xs text-amber-700 dark:text-amber-300">
                DEBUG code：{smsDevCode}
              </div>
            ) : null}
          </div>

          <Input
            label="验证码"
            value={smsCode}
            onChange={(e) => setSmsCode(e.target.value)}
            placeholder="请输入收到的验证码"
            disabled={smsVerifyMutation.isPending}
          />

          <div className="flex gap-2">
            <Button
              type="button"
              className="flex-1"
              isLoading={smsVerifyMutation.isPending}
              loadingText="验证中..."
              disabled={
                smsVerifyMutation.isPending || smsSendMutation.isPending
              }
              onClick={() => {
                const phone = String(smsPhone || "").trim();
                const code = String(smsCode || "").trim();
                if (!phone) {
                  toast.error("请输入手机号");
                  return;
                }
                if (!code) {
                  toast.error("请输入验证码");
                  return;
                }
                smsVerifyMutation.mutate(
                  { phone, code },
                  {
                    onSuccess: async () => {
                      toast.success("手机号验证成功");
                      setShowPhoneVerifyModal(false);
                      setFormData((prev) => ({ ...prev, phone }));
                      await refreshUser();
                    },
                  }
                );
              }}
            >
              确认绑定
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="flex-1"
              disabled={
                smsVerifyMutation.isPending || smsSendMutation.isPending
              }
              onClick={() => setShowPhoneVerifyModal(false)}
            >
              取消
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEditPostModal}
        onClose={() => {
          if (updateMyPostMutation.isPending) return;
          closeEditPost();
        }}
        title="编辑帖子"
        description="修改帖子标题、分类和内容"
        size="lg"
      >
        <form onSubmit={handleEditPostSubmit} className="space-y-5">
          <Input
            label="标题"
            value={editPostForm.title}
            onChange={(e) =>
              setEditPostForm((prev) => ({ ...prev, title: e.target.value }))
            }
            placeholder="请输入标题"
            className="py-3"
            disabled={updateMyPostMutation.isPending}
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              分类
            </label>
            <select
              value={editPostForm.category}
              onChange={(e) =>
                setEditPostForm((prev) => ({
                  ...prev,
                  category: e.target.value,
                }))
              }
              disabled={updateMyPostMutation.isPending}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
            >
              {postCategories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <Textarea
            label="内容"
            value={editPostForm.content}
            onChange={(e) =>
              setEditPostForm((prev) => ({ ...prev, content: e.target.value }))
            }
            placeholder="请输入内容"
            className="min-h-[220px]"
            disabled={updateMyPostMutation.isPending}
          />

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={closeEditPost}
              className="flex-1"
              disabled={updateMyPostMutation.isPending}
            >
              取消
            </Button>
            <Button
              type="submit"
              isLoading={updateMyPostMutation.isPending}
              loadingText="保存中..."
              disabled={updateMyPostMutation.isPending}
              className="flex-1"
            >
              保存
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={showPackModal}
        onClose={() => {
          if (buyPackMutation.isPending) return;
          setShowPackModal(false);
        }}
        title={
          packRelatedType === "document_generate"
            ? "购买文书生成次数包"
            : "购买 AI 咨询次数包"
        }
        description="请选择次数包档位"
        size="sm"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {(pricingQuery.data?.packs?.[packRelatedType] &&
              Array.isArray(pricingQuery.data?.packs?.[packRelatedType])
              ? pricingQuery.data?.packs?.[packRelatedType]
              : ([
                { count: 10, price: 12 },
                { count: 50, price: 49 },
                { count: 100, price: 79 },
              ] as PricingPackItem[])
            ).map((opt) => (
              <Button
                key={opt.count}
                type="button"
                variant="outline"
                disabled={buyPackMutation.isPending}
                onClick={() => handleConfirmBuyPack(opt)}
              >
                {opt.price
                  ? `${opt.count}次 (¥${Number(opt.price || 0).toFixed(2)})`
                  : `${opt.count}次`}
              </Button>
            ))}
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => setShowPackModal(false)}
            disabled={buyPackMutation.isPending}
            className="w-full"
          >
            取消
          </Button>
        </div>
      </Modal>

      {/* 密码修改弹窗 */}
      <Modal
        isOpen={showPasswordModal}
        onClose={() => {
          if (changePasswordMutation.isPending) return;
          setShowPasswordModal(false);
          setPasswordForm({
            old_password: "",
            new_password: "",
            confirm_password: "",
          });
        }}
        title="修改密码"
        description="请输入当前密码和新密码"
        size="sm"
      >
        <form onSubmit={handlePasswordChange} className="space-y-5">
          <div className="space-y-1">
            <label className="text-sm text-slate-700 dark:text-white/70">
              当前密码
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400 dark:text-white/40" />
              <input
                type={showOldPassword ? "text" : "password"}
                value={passwordForm.old_password}
                onChange={(e) =>
                  setPasswordForm({
                    ...passwordForm,
                    old_password: e.target.value,
                  })
                }
                disabled={changePasswordMutation.isPending}
                className="w-full pl-10 pr-10 py-3 bg-white border border-slate-200/70 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:border-amber-600/50 dark:bg-[#0f0a1e]/60 dark:border-white/10 dark:text-white dark:placeholder-white/30 dark:focus:border-amber-500/50"
                placeholder="请输入当前密码"
                required
              />
              <button
                type="button"
                onClick={() => setShowOldPassword(!showOldPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:text-white/40 dark:hover:text-white/60"
              >
                {showOldPassword ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm text-slate-700 dark:text-white/70">
              新密码
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400 dark:text-white/40" />
              <input
                type={showNewPassword ? "text" : "password"}
                value={passwordForm.new_password}
                onChange={(e) =>
                  setPasswordForm({
                    ...passwordForm,
                    new_password: e.target.value,
                  })
                }
                disabled={changePasswordMutation.isPending}
                className="w-full pl-10 pr-10 py-3 bg-white border border-slate-200/70 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:border-amber-600/50 dark:bg-[#0f0a1e]/60 dark:border-white/10 dark:text-white dark:placeholder-white/30 dark:focus:border-amber-500/50"
                placeholder="请输入新密码（至少6位）"
                required
                minLength={6}
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:text-white/40 dark:hover:text-white/60"
              >
                {showNewPassword ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm text-slate-700 dark:text-white/70">
              确认新密码
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400 dark:text-white/40" />
              <input
                type="password"
                value={passwordForm.confirm_password}
                onChange={(e) =>
                  setPasswordForm({
                    ...passwordForm,
                    confirm_password: e.target.value,
                  })
                }
                disabled={changePasswordMutation.isPending}
                className="w-full pl-10 pr-4 py-3 bg-white border border-slate-200/70 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:border-amber-600/50 dark:bg-[#0f0a1e]/60 dark:border-white/10 dark:text-white dark:placeholder-white/30 dark:focus:border-amber-500/50"
                placeholder="请再次输入新密码"
                required
              />
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                if (changePasswordMutation.isPending) return;
                setShowPasswordModal(false);
                setPasswordForm({
                  old_password: "",
                  new_password: "",
                  confirm_password: "",
                });
              }}
              className="flex-1"
              disabled={changePasswordMutation.isPending}
            >
              取消
            </Button>
            <Button
              type="submit"
              isLoading={changePasswordMutation.isPending}
              loadingText="修改中..."
              className="flex-1"
              disabled={changePasswordMutation.isPending}
            >
              确认修改
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
