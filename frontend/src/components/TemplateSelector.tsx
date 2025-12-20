import { useMemo, useState, type ComponentType } from "react";
import {
  Scale,
  Briefcase,
  Heart,
  Home,
  ShoppingCart,
  Car,
  Building,
  FileText,
  HelpCircle,
  ChevronRight,
  X,
  Sparkles,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { getApiErrorMessage } from "../utils";
import { Card, Button } from "./ui";
import { queryKeys } from "../queryKeys";

interface Template {
  id: number;
  name: string;
  description: string | null;
  category: string;
  icon: string;
  questions: Array<string | { question: string; hint?: string | null }>;
  sort_order: number;
}

interface TemplateSelectorProps {
  onSelectQuestion: (question: string) => void;
  onClose: () => void;
  theme?: "dark" | "light";
}

const iconMap: Record<string, ComponentType<{ className?: string }>> = {
  Scale,
  Briefcase,
  Heart,
  Home,
  ShoppingCart,
  Car,
  Building,
  FileText,
  HelpCircle,
};

const categoryLabels: Record<string, { label: string; color: string }> = {
  劳动纠纷: { label: "劳动纠纷", color: "from-blue-500 to-cyan-500" },
  婚姻家庭: { label: "婚姻家庭", color: "from-pink-500 to-rose-500" },
  合同纠纷: { label: "合同纠纷", color: "from-amber-500 to-orange-500" },
  消费维权: { label: "消费维权", color: "from-green-500 to-emerald-500" },
  房产纠纷: { label: "房产纠纷", color: "from-purple-500 to-violet-500" },
  交通事故: { label: "交通事故", color: "from-red-500 to-rose-500" },
  其他: { label: "其他", color: "from-gray-500 to-slate-500" },
};

export default function TemplateSelector({
  onSelectQuestion,
  onClose,
  theme = "dark",
}: TemplateSelectorProps) {
  const isLight = theme === "light";
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(
    null
  );

  const templatesQuery = useQuery({
    queryKey: queryKeys.knowledgeTemplates(true),
    queryFn: async () => {
      const res = await api.get("/knowledge/templates", { params: { is_active: true } });
      const data = res.data;
      return (Array.isArray(data) ? data : []) as Template[];
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const templates = templatesQuery.data ?? [];
  const loadError = templatesQuery.isError ? getApiErrorMessage(templatesQuery.error, "模板加载失败，请稍后重试") : null;
  const loading = templatesQuery.isLoading;

  const categories = useMemo(() => [...new Set(templates.map((t) => t.category))], [templates]);
  const filteredTemplates = selectedCategory
    ? templates.filter((t) => t.category === selectedCategory)
    : templates;

  const handleSelectQuestion = (question: string) => {
    onSelectQuestion(question);
    onClose();
  };

  const getQuestionText = (
    value: string | { question: string; hint?: string | null }
  ) => {
    return typeof value === "string" ? value : value.question;
  };

  const getIcon = (iconName: string) => {
    const IconComponent = iconMap[iconName] || HelpCircle;
    return IconComponent;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/60 backdrop-blur-sm p-4">
      <Card
        variant="surface"
        padding="none"
        className={`w-full max-w-3xl max-h-[80vh] overflow-hidden rounded-2xl ${
          isLight ? "bg-white border border-gray-200 text-gray-900" : ""
        }`}
      >
        {/* 头部 */}
        <div
          className={`flex items-center justify-between px-6 py-4 border-b ${
            isLight ? "border-gray-200" : "border-white/10"
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isLight
                  ? "bg-emerald-600"
                  : "bg-gradient-to-br from-amber-500 to-orange-500"
              }`}
            >
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className={`text-lg font-semibold ${isLight ? "text-gray-900" : "text-white"}`}>
                选择咨询模板
              </h2>
              <p className={`text-sm ${isLight ? "text-gray-600" : "text-white/50"}`}>
                快速开始您的法律咨询
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`p-2 rounded-lg transition-colors ${
              isLight ? "hover:bg-gray-100" : "hover:bg-white/10"
            }`}
          >
            <X className={`h-5 w-5 ${isLight ? "text-gray-500" : "text-white/50"}`} />
          </button>
        </div>

        {/* 分类标签 */}
        <div
          className={`flex gap-2 px-6 py-3 border-b overflow-x-auto ${
            isLight ? "border-gray-200" : "border-white/5"
          }`}
        >
          <button
            onClick={() => {
              setSelectedCategory(null);
              setSelectedTemplate(null);
            }}
            className={`px-4 py-2 rounded-full text-sm whitespace-nowrap transition-all ${
              !selectedCategory
                ? (isLight ? "bg-emerald-600 text-white" : "bg-amber-500 text-white")
                : (isLight ? "bg-gray-100 text-gray-700 hover:bg-gray-200" : "bg-white/5 text-white/70 hover:bg-white/10")
            }`}
          >
            全部
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => {
                setSelectedCategory(cat);
                setSelectedTemplate(null);
              }}
              className={`px-4 py-2 rounded-full text-sm whitespace-nowrap transition-all ${
                selectedCategory === cat
                  ? (isLight ? "bg-emerald-600 text-white" : "bg-amber-500 text-white")
                  : (isLight ? "bg-gray-100 text-gray-700 hover:bg-gray-200" : "bg-white/5 text-white/70 hover:bg-white/10")
              }`}
            >
              {categoryLabels[cat]?.label || cat}
            </button>
          ))}
        </div>

        {/* 内容区域 */}
        <div className="p-6 overflow-y-auto max-h-[50vh]">
          {loading ? (
            <div className={`text-center py-12 ${isLight ? "text-gray-500" : "text-white/50"}`}>
              加载中...
            </div>
          ) : loadError ? (
            <div className="text-center py-12">
              <p className={`${isLight ? "text-gray-700" : "text-white/70"}`}>{loadError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => templatesQuery.refetch()}
                className="mt-4"
              >
                重试
              </Button>
            </div>
          ) : selectedTemplate ? (
            // 显示模板问题列表
            <div className="space-y-4">
              <button
                onClick={() => setSelectedTemplate(null)}
                className={`text-sm flex items-center gap-1 ${
                  isLight ? "text-emerald-700 hover:text-emerald-800" : "text-amber-400 hover:text-amber-300"
                }`}
              >
                ← 返回模板列表
              </button>
              <div className="flex items-center gap-3 mb-4">
                {(() => {
                  const Icon = getIcon(selectedTemplate.icon);
                  return <Icon className={`h-6 w-6 ${isLight ? "text-emerald-700" : "text-amber-400"}`} />;
                })()}
                <div>
                  <h3 className={`text-lg font-semibold ${isLight ? "text-gray-900" : "text-white"}`}>
                    {selectedTemplate.name}
                  </h3>
                  {selectedTemplate.description && (
                    <p className={`text-sm mt-1 ${isLight ? "text-gray-600" : "text-white/50"}`}>
                      {selectedTemplate.description}
                    </p>
                  )}
                </div>
              </div>
              <div className="grid gap-3">
                {selectedTemplate.questions.map((question, idx) =>
                  (() => {
                    const questionText = getQuestionText(question);
                    return (
                      <button
                        key={idx}
                        onClick={() => handleSelectQuestion(questionText)}
                        className={`flex items-center justify-between p-4 rounded-xl transition-all text-left group ${
                          isLight
                            ? "bg-white hover:bg-gray-50 border border-gray-200 hover:border-emerald-300"
                            : "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber-500/50"
                        }`}
                      >
                        <span className={isLight ? "text-gray-900" : "text-white/90"}>{questionText}</span>
                        <ChevronRight
                          className={`h-5 w-5 transition-colors ${
                            isLight
                              ? "text-gray-400 group-hover:text-emerald-700"
                              : "text-white/30 group-hover:text-amber-400"
                          }`}
                        />
                      </button>
                    );
                  })()
                )}
              </div>
            </div>
          ) : (
            // 显示模板卡片
            <div className="grid sm:grid-cols-2 gap-4">
              {filteredTemplates.map((template) => {
                const Icon = getIcon(template.icon);
                const catColor =
                  categoryLabels[template.category]?.color ||
                  "from-gray-500 to-slate-500";
                return (
                  <button
                    key={template.id}
                    onClick={() => setSelectedTemplate(template)}
                    className={`flex items-start gap-4 p-4 rounded-xl transition-all text-left group ${
                      isLight
                        ? "bg-white hover:bg-gray-50 border border-gray-200 hover:border-emerald-300"
                        : "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber-500/30"
                    }`}
                  >
                    <div
                      className={`w-12 h-12 rounded-xl bg-gradient-to-br ${catColor} flex items-center justify-center flex-shrink-0`}
                    >
                      <Icon className="h-6 w-6 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3
                        className={`font-medium transition-colors ${
                          isLight
                            ? "text-gray-900 group-hover:text-emerald-700"
                            : "text-white group-hover:text-amber-400"
                        }`}
                      >
                        {template.name}
                      </h3>
                      <p className={`text-sm mt-1 line-clamp-2 ${isLight ? "text-gray-600" : "text-white/50"}`}>
                        {template.description}
                      </p>
                      <span
                        className={`inline-block mt-2 px-2 py-0.5 rounded text-xs ${
                          isLight ? "bg-gray-100 text-gray-700" : "bg-white/10 text-white/60"
                        }`}
                      >
                        {template.questions.length} 个问题
                      </span>
                    </div>
                    <ChevronRight
                      className={`h-5 w-5 transition-colors mt-1 ${
                        isLight
                          ? "text-gray-400 group-hover:text-emerald-700"
                          : "text-white/30 group-hover:text-amber-400"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 底部提示 */}
        <div
          className={`px-6 py-3 border-t text-center text-sm ${
            isLight ? "border-gray-200 text-gray-500" : "border-white/10 text-white/40"
          }`}
        >
          选择问题后将自动填入对话框，您也可以自由输入问题
        </div>
      </Card>
    </div>
  );
}
