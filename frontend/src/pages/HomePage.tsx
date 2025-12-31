import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  MessageCircle,
  Building2,
  Users,
  Newspaper,
  Shield,
  Clock,
  Award,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import { Badge, Card, LinkButton, Skeleton } from "../components/ui";
import api from "../api/client";
import { queryKeys } from "../queryKeys";

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
  const services = [
    {
      icon: MessageCircle,
      title: "AI法律咨询",
      description: "智能AI助手，24小时在线解答您的法律问题",
      link: "/chat",
    },
    {
      icon: Users,
      title: "法律论坛",
      description: "与专业人士交流，分享法律经验与见解",
      link: "/forum",
    },
    {
      icon: Newspaper,
      title: "法律资讯",
      description: "最新法律政策解读与案例分析",
      link: "/news",
    },
    {
      icon: Building2,
      title: "律所查询",
      description: "查找您身边的专业律师事务所",
      link: "/lawfirm",
    },
  ];

  const features = [
    {
      icon: Shield,
      title: "专业可靠",
      description: "基于权威法律法规，提供准确专业的法律建议",
    },
    {
      icon: Clock,
      title: "全天候服务",
      description: "7×24小时在线，随时为您解答法律疑问",
    },
    {
      icon: Award,
      title: "值得信赖",
      description: "已服务超过10万用户，获得广泛好评",
    },
  ];

  return (
    <div className="w-full space-y-0">
      {/* Hero Section */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        <div className="max-w-4xl mx-auto text-center px-4 animate-fade-in">
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-slate-900 dark:text-white leading-[1.1] tracking-tight">
            专业法律服务
            <span className="block mt-6 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 bg-clip-text text-transparent animate-gradient">
              触手可及
            </span>
          </h1>

          <p className="mt-10 text-xl md:text-2xl text-slate-600 dark:text-white/50 leading-relaxed max-w-2xl mx-auto font-light">
            AI智能与专业律师团队，为您提供全方位法律咨询
          </p>

          <div className="mt-14 flex flex-wrap gap-5 justify-center">
            <LinkButton
              to="/chat"
              className="group rounded-full px-10 py-4 text-base font-medium hover:shadow-xl hover:shadow-amber-500/20 hover:scale-105 transition-all duration-300"
            >
              开始咨询
              <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </LinkButton>
            <LinkButton
              to="/lawfirm"
              variant="outline"
              className="rounded-full px-10 py-4 text-base font-medium hover:bg-slate-50 dark:hover:bg-white/5 transition-all duration-300"
            >
              查找律师
            </LinkButton>
          </div>
        </div>

        {/* Enhanced decorative gradient orbs */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-br from-amber-500/15 via-orange-500/10 to-transparent rounded-full blur-3xl -z-10 animate-pulse-slow dark:from-amber-500/10 dark:via-orange-500/6" />
        <div className="absolute top-1/4 right-1/4 w-[400px] h-[400px] bg-gradient-to-br from-orange-500/10 to-transparent rounded-full blur-3xl -z-10 animate-float dark:from-orange-500/6" />
        <div className="absolute bottom-1/4 left-1/4 w-[400px] h-[400px] bg-gradient-to-br from-amber-500/10 to-transparent rounded-full blur-3xl -z-10 animate-float-delayed dark:from-amber-500/6" />
      </section>

      {/* Spacer */}
      <div className="h-24 md:h-32" />

      {/* Services Section */}
      <section>
        <div className="text-center mb-20">
          <p className="text-amber-700 text-xs font-medium tracking-widest uppercase mb-5 dark:text-amber-400/80">
            我们的服务
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            全方位法律服务平台
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-10 lg:gap-12">
          {services.map(({ icon: Icon, title, description, link }) => (
            <Link
              key={title}
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
                  {title}
                </h3>
                <p className="text-slate-600 leading-relaxed text-sm dark:text-white/40">
                  {description}
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
            为什么选择我们
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            值得信赖的法律服务伙伴
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-14 lg:gap-20">
          {features.map(({ icon: Icon, title, description }) => (
            <div key={title} className="text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500/10 to-orange-500/5 flex items-center justify-center mx-auto mb-8">
                <Icon className="h-7 w-7 text-amber-400/80" />
              </div>
              <h3 className="text-base font-medium text-slate-900 mb-4 dark:text-white">
                {title}
              </h3>
              <p className="text-slate-600 leading-relaxed text-sm dark:text-white/40">
                {description}
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
              准备好开始了吗？
            </h2>
            <p className="text-slate-600 text-base mb-10 leading-relaxed dark:text-white/40">
              无论您面临何种法律问题，我们都随时准备为您提供帮助
            </p>
            <LinkButton
              to="/chat"
              className="rounded-full px-10 py-4 text-base hover:shadow-lg hover:shadow-amber-500/15 transition-all"
            >
              立即咨询
              <ArrowRight className="h-4 w-4" />
            </LinkButton>
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
