import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, Star, UserRound } from "lucide-react";
import PageHeader from "../components/PageHeader";
import api from "../api/client";
import { useTheme } from "../contexts/ThemeContext";
import { useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";
import { Badge, Button, Card, EmptyState, Loading, Pagination } from "../components/ui";
import LawyerBookingModal from "../components/LawyerBookingModal";

type LawyerDetail = {
  id: number;
  user_id?: number | null;
  firm_id?: number | null;
  name: string;
  avatar?: string | null;
  title?: string | null;
  license_no?: string | null;
  phone?: string | null;
  email?: string | null;
  introduction?: string | null;
  specialties?: string | null;
  experience_years?: number;
  case_count?: number;
  rating?: number;
  review_count?: number;
  consultation_fee?: number;
  is_verified?: boolean;
  is_active?: boolean;
  created_at?: string;
  firm_name?: string | null;
};

type ReviewItem = {
  id: number;
  lawyer_id: number;
  user_id: number;
  consultation_id?: number | null;
  rating: number;
  content?: string | null;
  created_at: string;
  username?: string | null;
};

type ReviewListResponse = {
  items: ReviewItem[];
  total: number;
  average_rating: number;
};

function fmtMaybeDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

export default function LawyerDetailPage() {
  const { lawyerId } = useParams<{ lawyerId: string }>();
  const { actualTheme } = useTheme();
  const toast = useToast();

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [bookingOpen, setBookingOpen] = useState(false);

  const detailQuery = useQuery<LawyerDetail | null>({
    queryKey: ["lawyer-detail", { lawyerId }] as const,
    enabled: !!lawyerId,
    queryFn: async () => {
      const res = await api.get(`/lawfirm/lawyers/${lawyerId}`);
      return (res.data || null) as LawyerDetail | null;
    },
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const reviewsQuery = useQuery<ReviewListResponse>({
    queryKey: ["lawyer-reviews", { lawyerId, page, pageSize }] as const,
    enabled: !!lawyerId,
    queryFn: async () => {
      const res = await api.get(`/lawfirm/lawyers/${lawyerId}/reviews`, {
        params: { page, page_size: pageSize },
      });
      const data = res.data || {};
      return {
        items: Array.isArray(data?.items) ? (data.items as ReviewItem[]) : [],
        total: Number(data?.total || 0),
        average_rating: Number(data?.average_rating || 0),
      } satisfies ReviewListResponse;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) =>
      prev ?? ({ items: [], total: 0, average_rating: 0 } satisfies ReviewListResponse),
  });

  useEffect(() => {
    if (!detailQuery.error) return;
    toast.error(getApiErrorMessage(detailQuery.error, "律师信息加载失败，请稍后重试"));
  }, [detailQuery.error, toast]);

  useEffect(() => {
    if (!reviewsQuery.error) return;
    toast.error(getApiErrorMessage(reviewsQuery.error, "评价列表加载失败，请稍后重试"));
  }, [reviewsQuery.error, toast]);

  const lawyer = detailQuery.data ?? null;

  const reviewsData: ReviewListResponse =
    reviewsQuery.data ?? ({ items: [], total: 0, average_rating: 0 } satisfies ReviewListResponse);
  const reviewItems = reviewsData.items;

  const total = reviewsData.total ?? 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  if (detailQuery.isLoading && !lawyer) {
    return <Loading text="加载中..." tone={actualTheme} />;
  }

  if (!lawyer) {
    const err = detailQuery.isError
      ? getApiErrorMessage(detailQuery.error, "律师信息加载失败，请稍后重试")
      : null;
    return (
      <EmptyState
        icon={UserRound}
        title={err ? "加载失败" : "律师不存在或已被删除"}
        description={err || "请返回律所页面重新选择"}
        tone={actualTheme}
        action={
          <Link to="/lawfirm">
            <Button variant="outline">返回律所</Button>
          </Link>
        }
      />
    );
  }

  const rating = Number(lawyer.rating || 0);
  const reviewCount = Number(lawyer.review_count || 0);

  return (
    <div className="space-y-10">
      <Link
        to={lawyer.firm_id ? `/lawfirm/${lawyer.firm_id}` : "/lawfirm"}
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回
      </Link>

      <PageHeader
        eyebrow="律师"
        title={lawyer.name}
        description={lawyer.title ? String(lawyer.title) : "律师详情与评价"}
        layout="mdStart"
        tone={actualTheme}
        right={
          <Button
            variant="primary"
            onClick={() => setBookingOpen(true)}
            disabled={bookingOpen}
          >
            预约咨询
          </Button>
        }
      />

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <Card variant="surface" padding="lg">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">{lawyer.name}</h2>
                  {lawyer.is_verified ? (
                    <Badge variant="success" size="sm" icon={BadgeCheck}>
                      已认证
                    </Badge>
                  ) : null}
                </div>
                <div className="mt-2 text-sm text-slate-600 dark:text-white/55">
                  {lawyer.firm_name ? <div>律所：{lawyer.firm_name}</div> : null}
                  {lawyer.specialties ? <div>擅长：{lawyer.specialties}</div> : null}
                  {typeof lawyer.experience_years === "number" ? (
                    <div>从业年限：{lawyer.experience_years} 年</div>
                  ) : null}
                  {typeof lawyer.consultation_fee === "number" ? (
                    <div>
                      咨询费用：{lawyer.consultation_fee > 0 ? `¥${lawyer.consultation_fee}/次` : "免费"}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="text-right">
                <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400 justify-end">
                  <Star className="h-5 w-5 fill-amber-600 dark:fill-amber-400" />
                  <span className="text-xl font-semibold">{rating.toFixed(1)}</span>
                </div>
                <div className="text-sm text-slate-500 dark:text-white/45">{reviewCount} 条评价</div>
              </div>
            </div>

            {lawyer.introduction ? (
              <div className="mt-6">
                <div className="text-sm font-medium text-slate-700 dark:text-white/70">简介</div>
                <div className="mt-2 text-slate-700 dark:text-white/70 whitespace-pre-wrap">
                  {lawyer.introduction}
                </div>
              </div>
            ) : null}
          </Card>

          <Card variant="surface" padding="lg">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-lg font-semibold text-slate-900 dark:text-white">用户评价</div>
                <div className="mt-1 text-sm text-slate-600 dark:text-white/55">
                  平均评分：{Number(reviewsData.average_rating ?? 0).toFixed(1)}
                </div>
              </div>
              <Button variant="outline" onClick={() => reviewsQuery.refetch()} disabled={reviewsQuery.isFetching}>
                刷新
              </Button>
            </div>

            {reviewsQuery.isLoading && reviewItems.length === 0 ? (
              <Loading text="加载中..." />
            ) : reviewItems.length === 0 ? (
              <EmptyState
                icon={Star}
                title="暂无评价"
                description="该律师还没有收到用户评价"
                tone={actualTheme}
              />
            ) : (
              <div className="mt-6 space-y-4">
                {reviewItems.map((r) => (
                  <Card
                    key={r.id}
                    variant="surface"
                    padding="md"
                    className="border border-slate-200/70 dark:border-white/10"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {r.username ? r.username : "匿名用户"}
                          </div>
                          <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                            {Array.from({ length: 5 }).map((_, i) => {
                              const v = i + 1;
                              const active = v <= Number(r.rating || 0);
                              return (
                                <Star
                                  key={v}
                                  className={`h-4 w-4 ${active ? "fill-current" : ""}`}
                                />
                              );
                            })}
                          </div>
                        </div>
                        {r.content ? (
                          <div className="mt-2 text-sm text-slate-700 dark:text-white/70 whitespace-pre-wrap">
                            {r.content}
                          </div>
                        ) : null}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-white/40 whitespace-nowrap">
                        {fmtMaybeDate(r.created_at)}
                      </div>
                    </div>
                  </Card>
                ))}

                <div className="pt-2">
                  <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="lg:col-span-1">
          <Card variant="surface" padding="lg" className="sticky top-24">
            <div className="text-lg font-semibold text-slate-900 dark:text-white">预约咨询</div>
            <div className="mt-2 text-sm text-slate-600 dark:text-white/55">
              点击下方按钮提交预约，支付完成后等待律师确认接单。
            </div>
            <div className="mt-5">
              <Button variant="primary" className="w-full" onClick={() => setBookingOpen(true)}>
                立即预约
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {bookingOpen ? (
        <LawyerBookingModal
          lawyer={{
            id: lawyer.id,
            name: lawyer.name,
            title: lawyer.title ?? undefined,
            specialties: lawyer.specialties ?? undefined,
            consultation_fee: typeof lawyer.consultation_fee === "number" ? lawyer.consultation_fee : undefined,
          }}
          onClose={() => setBookingOpen(false)}
          onSuccess={() => toast.success("预约已提交")}
        />
      ) : null}
    </div>
  );
}
