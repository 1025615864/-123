import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  MessageCircle,
  Building2,
  Users,
  Newspaper,
  Search,
  Shield,
  Clock,
  Award,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import { Badge, Button, Card, Input, LinkButton, Skeleton } from "../components/ui";
import api from "../api/client";
import { queryKeys } from "../queryKeys";
import { toolNavItems } from "../navigation";
import { useLanguage } from "../contexts/LanguageContext";

interface HomeNewsListItem {
  id: number;
  title: string;
  category: string;
  is_top: boolean;
  view_count: number;
  published_at: string | null;
  created_at: string;
}

export default function HomePage() {
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const [searchKeyword, setSearchKeyword] = useState("");

  const quickQuestions =
    language === "en"
      ? [
          "I was fired during probation. What can I do?",
          "How are child custody and property divided in divorce?",
          "An online seller refused my refund. How to protect my rights?",
          "Someone owes me money. Can I sue with only bank transfer records?",
          "No contract for a year — can I claim double salary?",
          "Traffic accident (other party fully liable): what can I claim?",
        ]
      : [
          "试用期被辞退，公司不给补偿怎么办？",
          "离婚时房子和孩子抚养权怎么判？",
          "被网购商家拒绝退款，我该怎么维权？",
          "借钱不还，只有转账记录能起诉吗？",
          "劳动合同没签满一年，能要求双倍工资吗？",
          "交通事故对方全责，赔偿项目和标准有哪些？",
        ];

  const toolDescriptionKeys: Record<string, string> = {
    "/calculator": "home.toolDescriptions.calculator",
    "/limitations": "home.toolDescriptions.limitations",
    "/documents": "home.toolDescriptions.documents",
    "/calendar": "home.toolDescriptions.calendar",
  };

  const services = [
    {
      icon: MessageCircle,
      titleKey: "nav.consultation",
      descriptionKey: "home.services.consultationDescription",
      link: "/chat",
    },
    {
      icon: Users,
      titleKey: "nav.forum",
      descriptionKey: "home.services.forumDescription",
      link: "/forum",
    },
    {
      icon: Newspaper,
      titleKey: "nav.news",
      descriptionKey: "home.services.newsDescription",
      link: "/news",
    },
    {
      icon: Building2,
      titleKey: "nav.lawfirm",
      descriptionKey: "home.services.lawfirmDescription",
      link: "/lawfirm",
    },
  ];

  const features = [
    {
      icon: Shield,
      titleKey: "home.features.professionalTitle",
      descriptionKey: "home.features.professionalDescription",
    },
    {
      icon: Clock,
      titleKey: "home.features.alwaysOnTitle",
      descriptionKey: "home.features.alwaysOnDescription",
    },
    {
      icon: Award,
      titleKey: "home.features.trustedTitle",
      descriptionKey: "home.features.trustedDescription",
    },
  ];

  return (
    <div className="w-full space-y-0">
      {/* Hero Section */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        <div className="max-w-4xl mx-auto text-center px-4 animate-fade-in">
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-slate-900 dark:text-white leading-[1.1] tracking-tight">
            {t("home.heroTitle")}
            <span className="block mt-6 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 bg-clip-text text-transparent animate-gradient">
              {t("home.heroTitleAccent")}
            </span>
          </h1>

          <p className="mt-10 text-xl md:text-2xl text-slate-600 dark:text-white/50 leading-relaxed max-w-2xl mx-auto font-light">
            {t("home.heroSubtitle")}
          </p>

          <form
            className="mt-10 max-w-2xl mx-auto"
            onSubmit={(e) => {
              e.preventDefault();
              const kw = searchKeyword.trim();
              navigate(kw ? `/search?q=${encodeURIComponent(kw)}` : "/search");
            }}
          >
            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                icon={Search}
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                placeholder={t("home.searchPlaceholder")}
              />
              <Button type="submit" className="sm:w-28">
                {t("common.search")}
              </Button>
            </div>
          </form>

          <div className="mt-14 flex flex-wrap gap-5 justify-center">
            <LinkButton
              to="/chat"
              className="group rounded-full px-10 py-4 text-base font-medium hover:shadow-xl hover:shadow-amber-500/20 hover:scale-105 transition-all duration-300"
            >
              {t("layout.startConsultation")}
              <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </LinkButton>
            <LinkButton
              to="/lawfirm"
              variant="outline"
              className="rounded-full px-10 py-4 text-base font-medium hover:bg-slate-50 dark:hover:bg-white/5 transition-all duration-300"
            >
              {t("home.findLawyer")}
            </LinkButton>
            <Button
              type="button"
              variant="ghost"
              className="rounded-full px-8 py-4 text-base font-medium"
              onClick={() => {
                document.getElementById("home-tools")?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              {t("layout.tools")}
              <ArrowRight className="h-5 w-5" />
            </Button>
          </div>

          <div className="mt-10 max-w-3xl mx-auto">
            <div className="text-xs text-slate-500 dark:text-white/40 text-center">
              {t("home.quickQuestionsHint")}
            </div>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {quickQuestions.map((q) => (
                <Link
                  key={q}
                  to={`/chat?draft=${encodeURIComponent(q)}`}
                  className="px-3 py-2 rounded-full bg-white/70 border border-slate-200 text-slate-700 text-xs hover:bg-white hover:border-slate-300 active:scale-[0.99] transition-all outline-none focus-visible:ring-2 focus-visible:ring-amber-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-white/5 dark:border-white/10 dark:text-slate-200 dark:hover:bg-white/10 dark:focus-visible:ring-offset-slate-900"
                >
                  {q}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Enhanced decorative gradient orbs */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-br from-amber-500/15 via-orange-500/10 to-transparent rounded-full blur-3xl -z-10 animate-pulse-slow dark:from-amber-500/10 dark:via-orange-500/6" />
        <div className="absolute top-1/4 right-1/4 w-[400px] h-[400px] bg-gradient-to-br from-orange-500/10 to-transparent rounded-full blur-3xl -z-10 animate-float dark:from-orange-500/6" />
        <div className="absolute bottom-1/4 left-1/4 w-[400px] h-[400px] bg-gradient-to-br from-amber-500/10 to-transparent rounded-full blur-3xl -z-10 animate-float-delayed dark:from-amber-500/6" />
      </section>

      <section id="home-tools" className="pt-12 md:pt-16">
        <div className="text-center mb-16">
          <p className="text-amber-700 text-xs font-medium tracking-widest uppercase mb-5 dark:text-amber-400/80">
            {t("home.toolsEyebrow")}
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            {t("home.toolsTitle")}
          </h2>
          <p className="mt-4 text-slate-600 dark:text-white/50 text-sm max-w-2xl mx-auto">
            {t("home.toolsDescription")}
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {toolNavItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className="group block rounded-3xl outline-none focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900"
            >
              <Card variant="surface" hover padding="none" className="p-8">
                <div className="flex items-start justify-between gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/10 to-indigo-500/5 flex items-center justify-center">
                    <Icon className="h-6 w-6 text-blue-600/90 dark:text-blue-400" />
                  </div>
                  <Badge className="bg-blue-50 text-blue-700 border border-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-500/20">
                    {t("home.toolBadge")}
                  </Badge>
                </div>
                <h3 className="mt-6 text-base font-medium text-slate-900 group-hover:text-blue-600 transition-colors dark:text-white dark:group-hover:text-blue-400">
                  {t(label)}
                </h3>
                <p className="mt-3 text-slate-600 leading-relaxed text-sm dark:text-white/45">
                  {t(toolDescriptionKeys[path] ?? "home.toolDescriptions.default")}
                </p>
                <div className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-blue-600 dark:text-blue-400">
                  {t("home.toolAction")}
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <div className="h-24 md:h-32" />

      {/* Services Section */}
      <section>
        <div className="text-center mb-20">
          <p className="text-amber-700 text-xs font-medium tracking-widest uppercase mb-5 dark:text-amber-400/80">
            {t("home.services.eyebrow")}
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            {t("home.services.title")}
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-10 lg:gap-12">
          {services.map(({ icon: Icon, titleKey, descriptionKey, link }) => (
            <Link
              key={link}
              to={link}
              className="group block rounded-3xl outline-none focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900"
            >
              <Card
                variant="surface"
                hover
                padding="none"
                className="p-10 lg:p-12"
              >
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500/15 to-orange-500/5 flex items-center justify-center mb-8">
                  <Icon className="h-6 w-6 text-amber-400/90" />
                </div>
                <h3 className="text-lg font-medium text-slate-900 mb-4 group-hover:text-amber-600 transition-colors dark:text-white dark:group-hover:text-amber-400">
                  {t(titleKey)}
                </h3>
                <p className="text-slate-600 leading-relaxed text-sm dark:text-white/40">
                  {t(descriptionKey)}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Spacer */}
      <div className="h-32 md:h-40" />

      <HomeNewsRecommendSection />

      {/* Spacer */}
      <div className="h-32 md:h-40" />

      {/* Features Section */}
      <section className="border-t border-slate-200/70 pt-20 md:pt-28 dark:border-white/5">
        <div className="text-center mb-20">
          <p className="text-amber-700 text-xs font-medium tracking-widest uppercase mb-5 dark:text-amber-400/80">
            {t("home.features.eyebrow")}
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            {t("home.features.title")}
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-14 lg:gap-20">
          {features.map(({ icon: Icon, titleKey, descriptionKey }) => (
            <div key={titleKey} className="text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500/10 to-orange-500/5 flex items-center justify-center mx-auto mb-8">
                <Icon className="h-7 w-7 text-amber-400/80" />
              </div>
              <h3 className="text-base font-medium text-slate-900 mb-4 dark:text-white">
                {t(titleKey)}
              </h3>
              <p className="text-slate-600 leading-relaxed text-sm dark:text-white/40">
                {t(descriptionKey)}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Spacer */}
      <div className="h-32 md:h-40" />

      {/* CTA Section */}
      <section className="pb-16 md:pb-24">
        <div className="relative overflow-hidden rounded-3xl bg-white border border-slate-200/70 p-16 md:p-24 dark:bg-gradient-to-br dark:from-white/[0.02] dark:to-transparent dark:border-white/[0.04]">
          <div className="relative z-10 max-w-xl mx-auto text-center">
            <h2 className="text-2xl md:text-3xl font-medium text-slate-900 mb-6 dark:text-white">
              {t("home.cta.title")}
            </h2>
            <p className="text-slate-600 text-base mb-10 leading-relaxed dark:text-white/40">
              {t("home.cta.description")}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <LinkButton
                to="/chat"
                className="rounded-full px-10 py-4 text-base hover:shadow-lg hover:shadow-amber-500/15 transition-all"
              >
                {t("home.cta.consultNow")}
                <ArrowRight className="h-4 w-4" />
              </LinkButton>
              <LinkButton
                to="/search"
                variant="outline"
                className="rounded-full px-10 py-4 text-base"
              >
                {t("home.cta.search")}
              </LinkButton>
              <LinkButton
                to="/lawfirm"
                variant="outline"
                className="rounded-full px-10 py-4 text-base"
              >
                {t("home.cta.findLawyer")}
              </LinkButton>
            </div>
          </div>

          {/* Decorative element */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-br from-amber-500/7 to-transparent rounded-full blur-3xl dark:from-amber-500/5" />
        </div>
      </section>
    </div>
  );
}

function HomeNewsRecommendSection() {
  const topLimit = 5;
  const recentLimit = 6;
  const hotLimit = 6;
  const hotDays = 7;

  const topNewsQuery = useQuery({
    queryKey: queryKeys.newsTop(topLimit),
    queryFn: async () => {
      try {
        const res = await api.get(`/news/top?limit=${topLimit}`);
        return (Array.isArray(res.data) ? res.data : []) as HomeNewsListItem[];
      } catch {
        return [] as HomeNewsListItem[];
      }
    },
    staleTime: 2 * 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const recentNewsQuery = useQuery({
    queryKey: queryKeys.newsRecent(recentLimit),
    queryFn: async () => {
      try {
        const res = await api.get(`/news/recent?limit=${recentLimit}`);
        return (Array.isArray(res.data) ? res.data : []) as HomeNewsListItem[];
      } catch {
        return [] as HomeNewsListItem[];
      }
    },
    staleTime: 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const hotNewsQuery = useQuery({
    queryKey: queryKeys.newsHot(hotDays, hotLimit, null),
    queryFn: async () => {
      try {
        const res = await api.get(`/news/hot?days=${hotDays}&limit=${hotLimit}`);
        return (Array.isArray(res.data) ? res.data : []) as HomeNewsListItem[];
      } catch {
        return [] as HomeNewsListItem[];
      }
    },
    staleTime: 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const renderList = (items: HomeNewsListItem[], emptyText: string, showViews: boolean = false) => {
    if (items.length === 0) {
      return (
        <div className="text-sm text-slate-600 dark:text-white/45">
          {emptyText}
        </div>
      );
    }

    return (
      <div className="divide-y divide-slate-200/70 dark:divide-white/10">
        {items.map((item) => (
          <Link
            key={item.id}
            to={`/news/${item.id}`}
            className="group block rounded-xl px-3 -mx-3 py-4 transition-colors hover:bg-slate-50 dark:hover:bg-white/[0.03] outline-none focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900"
          >
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="primary" size="sm">
                {item.category}
              </Badge>
              {item.is_top ? (
                <Badge variant="warning" size="sm">
                  置顶
                </Badge>
              ) : null}
            </div>
            <div className="text-base font-medium text-slate-900 group-hover:text-amber-600 transition-colors line-clamp-2 dark:text-white dark:group-hover:text-amber-400">
              {item.title}
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-white/45">
              {new Date(
                item.published_at || item.created_at
              ).toLocaleDateString()}
              {showViews ? ` · 阅读 ${item.view_count}` : null}
            </div>
          </Link>
        ))}
      </div>
    );
  };

  const renderLoading = () => (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="py-4">
          <Skeleton width="35%" height="14px" />
          <Skeleton width="90%" height="18px" className="mt-2" />
          <Skeleton width="40%" height="12px" className="mt-2" />
        </div>
      ))}
    </div>
  );

  return (
    <section>
      <div className="flex items-end justify-between gap-6 mb-10">
        <div>
          <p className="text-amber-700 text-xs font-medium tracking-widest uppercase mb-4 dark:text-amber-400/80">
            法律资讯
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            推荐阅读
          </h2>
        </div>
        <LinkButton
          to="/news"
          variant="ghost"
          className="rounded-full px-6 py-3 text-sm transition-all hover:shadow-sm"
        >
          更多资讯
          <ArrowRight className="h-4 w-4" />
        </LinkButton>
      </div>

      <div className="grid lg:grid-cols-3 gap-10">
        <Card variant="surface" className="p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-500/15 to-orange-500/5 flex items-center justify-center">
              <Newspaper className="h-5 w-5 text-amber-400/90" />
            </div>
            <div>
              <div className="text-lg font-medium text-slate-900 dark:text-white">
                置顶新闻
              </div>
              <div className="text-sm text-slate-600 dark:text-white/45">
                重点政策与解读
              </div>
            </div>
          </div>
          {topNewsQuery.isLoading
            ? renderLoading()
            : renderList(topNewsQuery.data ?? [], "暂无置顶新闻")}
        </Card>

        <Card variant="surface" className="p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-500/15 to-orange-500/5 flex items-center justify-center">
              <Clock className="h-5 w-5 text-amber-400/90" />
            </div>
            <div>
              <div className="text-lg font-medium text-slate-900 dark:text-white">
                最新新闻
              </div>
              <div className="text-sm text-slate-600 dark:text-white/45">
                最近发布
              </div>
            </div>
          </div>
          {recentNewsQuery.isLoading
            ? renderLoading()
            : renderList(recentNewsQuery.data ?? [], "暂无最新新闻")}
        </Card>

        <Card variant="surface" className="p-8" data-testid="home-news-hot">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-500/15 to-orange-500/5 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-amber-400/90" />
            </div>
            <div>
              <div className="text-lg font-medium text-slate-900 dark:text-white">
                热门新闻
              </div>
              <div className="text-sm text-slate-600 dark:text-white/45">
                近7天阅读最多
              </div>
            </div>
          </div>
          {hotNewsQuery.isLoading
            ? renderLoading()
            : renderList(hotNewsQuery.data ?? [], "暂无热门新闻", true)}
        </Card>
      </div>
    </section>
  );
}
