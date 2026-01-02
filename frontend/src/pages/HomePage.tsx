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
  const [searchKeyword, setSearchKeyword] = useState("");

  const quickQuestions = [
    "试用期被辞退，公司不给补偿怎么办？",
    "离婚时房子和孩子抚养权怎么判？",
    "被网购商家拒绝退款，我该怎么维权？",
    "借钱不还，只有转账记录能起诉吗？",
    "劳动合同没签满一年，能要求双倍工资吗？",
    "交通事故对方全责，赔偿项目和标准有哪些？",
  ];

  const toolDescriptions: Record<string, string> = {
    "/calculator": "快速估算费用区间，避免踩坑",
    "/limitations": "一键计算诉讼时效，防止过期",
    "/documents": "模板化生成文书，提升效率",
    "/calendar": "重要节点提醒，不错过关键时间",
  };

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
                placeholder="搜索新闻、帖子、律所、律师与知识库..."
              />
              <Button type="submit" className="sm:w-28">
                搜索
              </Button>
            </div>
          </form>

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
            <Button
              type="button"
              variant="ghost"
              className="rounded-full px-8 py-4 text-base font-medium"
              onClick={() => {
                document.getElementById("home-tools")?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              法律工具
              <ArrowRight className="h-5 w-5" />
            </Button>
          </div>

          <div className="mt-10 max-w-3xl mx-auto">
            <div className="text-xs text-slate-500 dark:text-white/40 text-center">
              试试这样问（点击一键带入 AI 咨询）
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
            常用法律工具
          </p>
          <h2 className="text-2xl md:text-3xl font-medium text-slate-900 dark:text-white">
            一站式解决高频问题
          </h2>
          <p className="mt-4 text-slate-600 dark:text-white/50 text-sm max-w-2xl mx-auto">
            先用工具快速自查，再进入 AI 咨询获得更完整的建议
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
                    工具
                  </Badge>
                </div>
                <h3 className="mt-6 text-base font-medium text-slate-900 group-hover:text-blue-600 transition-colors dark:text-white dark:group-hover:text-blue-400">
                  {label}
                </h3>
                <p className="mt-3 text-slate-600 leading-relaxed text-sm dark:text-white/45">
                  {toolDescriptions[path] ?? "打开工具，快速完成计算与生成"}
                </p>
                <div className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-blue-600 dark:text-blue-400">
                  立即使用
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
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <LinkButton
                to="/chat"
                className="rounded-full px-10 py-4 text-base hover:shadow-lg hover:shadow-amber-500/15 transition-all"
              >
                立即咨询
                <ArrowRight className="h-4 w-4" />
              </LinkButton>
              <LinkButton
                to="/search"
                variant="outline"
                className="rounded-full px-10 py-4 text-base"
              >
                去搜索
              </LinkButton>
              <LinkButton
                to="/lawfirm"
                variant="outline"
                className="rounded-full px-10 py-4 text-base"
              >
                找律师
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
