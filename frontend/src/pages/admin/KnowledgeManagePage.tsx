import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Search,
  Plus,
  Edit,
  Trash2,
  Database,
  BookOpen,
  Scale,
  FileText,
  Upload,
  Check,
} from "lucide-react";
import {
  Card,
  Input,
  Button,
  Badge,
  Modal,
  Textarea,
  Pagination,
} from "../../components/ui";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import { useAppMutation, useToast } from "../../hooks";
import { getApiErrorMessage } from "../../utils";
import { queryKeys } from "../../queryKeys";

type KnowledgeType = "law" | "case" | "regulation" | "interpretation";

interface KnowledgeUpsertPayload {
  knowledge_type: KnowledgeType;
  title: string;
  article_number: string | null;
  content: string;
  summary: string | null;
  category: string;
  keywords: string | null;
  source: string | null;
  effective_date: string | null;
  weight: number;
  is_active: boolean;
}

interface LegalKnowledge {
  id: number;
  knowledge_type: KnowledgeType;
  title: string;
  article_number: string | null;
  content: string;
  summary: string | null;
  category: string;
  keywords: string | null;
  source: string | null;
  effective_date: string | null;
  weight: number;
  is_active: boolean;
  is_vectorized: boolean;
  created_at: string;
  updated_at: string;
}

interface KnowledgeStats {
  total_laws: number;
  total_cases: number;
  total_regulations: number;
  total_interpretations: number;
  vectorized_count: number;
  categories: Array<{ category: string; count: number }>;
}

interface VectorStoreStatus {
  openai_api_key_configured: boolean;
  chroma_persist_dir: string;
  persist_dir_exists: boolean;
  initialized: boolean;
  embeddings_ready: boolean;
  vector_store_ready: boolean;
  collection_name: string | null;
  collection_count: number | null;
  error: string | null;
}

interface BatchOperationResult {
  success_count: number;
  failed_count: number;
  message: string;
}

const KNOWLEDGE_TYPES: {
  value: KnowledgeType;
  label: string;
  icon: typeof BookOpen;
}[] = [
  { value: "law", label: "法律条文", icon: Scale },
  { value: "case", label: "案例", icon: FileText },
  { value: "regulation", label: "法规规章", icon: BookOpen },
  { value: "interpretation", label: "司法解释", icon: Database },
];

const DEFAULT_CATEGORIES = [
  "民法",
  "刑法",
  "劳动法",
  "婚姻家庭",
  "合同法",
  "知识产权",
  "行政法",
  "经济法",
  "诉讼法",
  "其他",
];

export default function KnowledgeManagePage() {
  const [keyword, setKeyword] = useState("");
  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingItem, setEditingItem] = useState<LegalKnowledge | null>(null);
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const pageSize = 20;

  const toast = useToast();

  const statsQueryKey = useMemo(() => queryKeys.knowledgeStats(), []);
  const listQueryKey = useMemo(
    () => queryKeys.adminKnowledgeList(page, pageSize, keyword.trim(), selectedType, selectedCategory),
    [page, pageSize, keyword, selectedCategory, selectedType]
  );

  const statsQuery = useQuery({
    queryKey: statsQueryKey,
    queryFn: async () => {
      const res = await api.get("/knowledge/stats");
      return res.data as KnowledgeStats;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const vectorStoreStatusQuery = useQuery({
    queryKey: useMemo(() => queryKeys.knowledgeVectorStoreStatus(), []),
    queryFn: async () => {
      const res = await api.get("/knowledge/vector-store/status");
      return res.data as VectorStoreStatus;
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  const listQuery = useQuery({
    queryKey: listQueryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      if (keyword) params.append("keyword", keyword);
      if (selectedType) params.append("knowledge_type", selectedType);
      if (selectedCategory) params.append("category", selectedCategory);

      const res = await api.get(`/knowledge/laws?${params.toString()}`);
      const data = res.data;
      return {
        items: Array.isArray(data?.items) ? (data.items as LegalKnowledge[]) : ([] as LegalKnowledge[]),
        total: Number(data?.total || 0),
      };
    },
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    const err = statsQuery.error || listQuery.error || vectorStoreStatusQuery.error;
    if (!err) return;
    toast.error(getApiErrorMessage(err));
  }, [listQuery.error, statsQuery.error, toast, vectorStoreStatusQuery.error]);

  const stats = statsQuery.data ?? null;
  const knowledge = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const loading = listQuery.isLoading;
  const vectorStoreStatus = vectorStoreStatusQuery.data ?? null;

  const createMutation = useAppMutation<void, KnowledgeUpsertPayload>({
    mutationFn: async (payload) => {
      await api.post("/knowledge/laws", payload);
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.adminKnowledgeListRoot(), queryKeys.knowledgeStats()],
    onSuccess: () => {
      setShowCreateModal(false);
      resetForm();
    },
  });

  const editMutation = useAppMutation<
    void,
    { id: number; payload: KnowledgeUpsertPayload }
  >({
    mutationFn: async ({ id, payload }) => {
      await api.put(`/knowledge/laws/${id}`, payload);
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.adminKnowledgeListRoot(), queryKeys.knowledgeStats()],
    onSuccess: () => {
      setShowEditModal(false);
      setEditingItem(null);
      resetForm();
    },
  });

  const deleteMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/knowledge/laws/${id}`);
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.adminKnowledgeListRoot(), queryKeys.knowledgeStats()],
  });

  const syncAllMutation = useAppMutation<BatchOperationResult, void>({
    mutationFn: async (_: void) => {
      const res = await api.post("/knowledge/sync-vector-store", {});
      return res.data as BatchOperationResult;
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [
      queryKeys.adminKnowledgeListRoot(),
      queryKeys.knowledgeStats(),
      queryKeys.knowledgeVectorStoreStatus(),
    ],
    onSuccess: (data) => {
      const msg = String(data?.message ?? "").trim();
      if (msg) {
        toast.success(msg);
      } else {
        toast.success("同步完成");
      }

      const failed = Number(data?.failed_count ?? 0);
      if (failed > 0) {
        toast.warning("部分条目同步失败，可查看下方“向量库状态”的错误信息");
      }
    },
    onError: async () => {
      try {
        const res = await api.get("/knowledge/vector-store/status");
        const status = res.data as VectorStoreStatus;
        const err = String(status?.error ?? "").trim();

        if (!status?.openai_api_key_configured) {
          toast.warning("OPENAI_API_KEY 未配置：无法进行向量化/同步");
          return;
        }
        if (err) {
          toast.warning(`向量库状态异常：${err}`);
        }
      } catch {
        // ignore
      }
    },
  });

  const importSeedMutation = useAppMutation<void, void>({
    mutationFn: async (_: void) => {
      await api.post("/knowledge/laws/import-seed", {});
    },
    successMessage: "导入完成",
    errorMessageFallback: "导入失败，请稍后重试",
    invalidateQueryKeys: [
      queryKeys.adminKnowledgeListRoot(),
      queryKeys.knowledgeStats(),
      queryKeys.knowledgeVectorStoreStatus(),
    ],
    onSuccess: () => {
      if (
        confirm(
          "示例法条已导入。是否立即同步向量库？\n\n提示：同步向量库需要已配置 AI Embeddings（如 OPENAI_API_KEY/OPENAI_BASE_URL）。"
        )
      ) {
        if (!syncAllMutation.isPending) {
          syncAllMutation.mutate();
        }
      }
    },
  });

  const batchVectorizeMutation = useAppMutation<void, number[]>({
    mutationFn: async (ids) => {
      await api.post("/knowledge/laws/batch-vectorize", { ids });
    },
    errorMessageFallback: "操作失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.adminKnowledgeListRoot(), queryKeys.knowledgeStats()],
    onSuccess: () => {
      setSelectedIds([]);
    },
  });

  // 表单状态
  const [formData, setFormData] = useState({
    knowledge_type: "law" as KnowledgeType,
    title: "",
    article_number: "",
    content: "",
    summary: "",
    category: "民法",
    keywords: "",
    source: "",
    effective_date: "",
    weight: 1,
    is_active: true,
  });

  const normalizePayload = useCallback(
    (raw: typeof formData): KnowledgeUpsertPayload => {
      const title = String(raw.title ?? "").trim();
      const content = String(raw.content ?? "").trim();
      const category = String(raw.category ?? "").trim();
      return {
        knowledge_type: raw.knowledge_type,
        title,
        article_number: String(raw.article_number ?? "").trim() || null,
        content,
        summary: String(raw.summary ?? "").trim() || null,
        category,
        keywords: String(raw.keywords ?? "").trim() || null,
        source: String(raw.source ?? "").trim() || null,
        effective_date: String(raw.effective_date ?? "").trim() || null,
        weight: Number(raw.weight) || 1,
        is_active: Boolean(raw.is_active),
      };
    },
    []
  );

  const handleCreate = async () => {
    if (createMutation.isPending) return;
    createMutation.mutate(normalizePayload(formData));
  };

  const handleEdit = async () => {
    if (!editingItem) return;
    if (editMutation.isPending) return;
    editMutation.mutate({
      id: editingItem.id,
      payload: normalizePayload(formData),
    });
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定要删除这条知识吗？")) return;
    if (deleteMutation.isPending) return;
    deleteMutation.mutate(id);
  };

  const handleBatchVectorize = async () => {
    if (selectedIds.length === 0) return;
    if (batchVectorizeMutation.isPending) return;
    batchVectorizeMutation.mutate(selectedIds);
  };

  const handleSyncAll = async () => {
    if (syncAllMutation.isPending) return;
    syncAllMutation.mutate();
  };

  const handleImportSeed = async () => {
    if (importSeedMutation.isPending) return;
    if (!confirm("将导入内置示例法条到数据库（会跳过重复项）。是否继续？")) return;
    importSeedMutation.mutate();
  };

  const openEditModal = (item: LegalKnowledge) => {
    setEditingItem(item);
    setFormData({
      knowledge_type: item.knowledge_type,
      title: item.title,
      article_number: item.article_number || "",
      content: item.content,
      summary: item.summary || "",
      category: item.category,
      keywords: item.keywords || "",
      source: item.source || "",
      effective_date: item.effective_date || "",
      weight: item.weight,
      is_active: item.is_active,
    });
    setShowEditModal(true);
  };

  const resetForm = () => {
    setFormData({
      knowledge_type: "law",
      title: "",
      article_number: "",
      content: "",
      summary: "",
      category: "民法",
      keywords: "",
      source: "",
      effective_date: "",
      weight: 1,
      is_active: true,
    });
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const getTypeLabel = (type: KnowledgeType) => {
    return KNOWLEDGE_TYPES.find((t) => t.value === type)?.label || type;
  };

  const getTypeBadgeVariant = (type: KnowledgeType) => {
    const variants: Record<
      KnowledgeType,
      "primary" | "success" | "info" | "warning"
    > = {
      law: "primary",
      case: "success",
      regulation: "info",
      interpretation: "warning",
    };
    return variants[type];
  };

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">知识库管理</h1>
          <p className="text-slate-600 mt-1 dark:text-white/50">管理法律条文、案例和司法解释</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" icon={Upload} onClick={handleImportSeed} disabled={importSeedMutation.isPending}>
            导入示例法条
          </Button>
          <Button variant="outline" icon={Upload} onClick={handleSyncAll}>
            同步向量库
          </Button>
          <Button icon={Plus} onClick={() => setShowCreateModal(true)}>
            添加知识
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card variant="surface" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-500/20">
                <Scale className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <p className="text-slate-600 text-sm dark:text-white/50">法律条文</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {stats.total_laws}
                </p>
              </div>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-500/20">
                <FileText className="h-5 w-5 text-green-400" />
              </div>
              <div>
                <p className="text-slate-600 text-sm dark:text-white/50">案例</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {stats.total_cases}
                </p>
              </div>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-500/20">
                <BookOpen className="h-5 w-5 text-purple-400" />
              </div>
              <div>
                <p className="text-slate-600 text-sm dark:text-white/50">法规规章</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {stats.total_regulations}
                </p>
              </div>
            </div>
          </Card>
          <Card variant="surface" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-500/20">
                <Database className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <p className="text-slate-600 text-sm dark:text-white/50">已向量化</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {stats.vectorized_count}
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 向量库状态 */}
      <Card variant="surface" padding="md">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">向量库状态</h2>
            <p className="text-slate-600 text-sm mt-1 dark:text-white/50">
              用于诊断同步向量库前的配置与可用性
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => vectorStoreStatusQuery.refetch()}
            disabled={vectorStoreStatusQuery.isFetching}
          >
            刷新
          </Button>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="flex items-center justify-between rounded-xl border border-slate-200/70 px-4 py-3 dark:border-white/10">
            <span className="text-sm text-slate-600 dark:text-white/50">OPENAI_API_KEY 已配置</span>
            <Badge variant={vectorStoreStatus?.openai_api_key_configured ? "success" : "warning"}>
              {vectorStoreStatus?.openai_api_key_configured ? "是" : "否"}
            </Badge>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-slate-200/70 px-4 py-3 dark:border-white/10">
            <span className="text-sm text-slate-600 dark:text-white/50">Chroma 目录存在</span>
            <Badge variant={vectorStoreStatus?.persist_dir_exists ? "success" : "warning"}>
              {vectorStoreStatus?.persist_dir_exists ? "是" : "否"}
            </Badge>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-slate-200/70 px-4 py-3 dark:border-white/10">
            <span className="text-sm text-slate-600 dark:text-white/50">Embeddings 就绪</span>
            <Badge variant={vectorStoreStatus?.embeddings_ready ? "success" : "warning"}>
              {vectorStoreStatus?.embeddings_ready ? "是" : "否"}
            </Badge>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-slate-200/70 px-4 py-3 dark:border-white/10">
            <span className="text-sm text-slate-600 dark:text-white/50">Vector Store 就绪</span>
            <Badge variant={vectorStoreStatus?.vector_store_ready ? "success" : "warning"}>
              {vectorStoreStatus?.vector_store_ready ? "是" : "否"}
            </Badge>
          </div>
        </div>

        <div className="mt-3 text-sm text-slate-700 dark:text-white/70">
          <div className="truncate">
            Chroma 目录：{vectorStoreStatus?.chroma_persist_dir || "(未配置)"}
          </div>
          <div>
            Collection：{vectorStoreStatus?.collection_name || "(未知)"}
            {typeof vectorStoreStatus?.collection_count === "number" ? `，文档数：${vectorStoreStatus.collection_count}` : ""}
          </div>
          {vectorStoreStatus?.error ? (
            <div className="mt-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
              {vectorStoreStatus.error}
            </div>
          ) : null}
        </div>
      </Card>

      {/* 筛选和列表 */}
      <Card variant="surface" padding="md">
        <div className="flex flex-wrap gap-4 mb-6">
          <div className="flex-1 min-w-[200px] max-w-md">
            <Input
              icon={Search}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索标题、内容..."
            />
          </div>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-4 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
          >
            <option value="">全部类型</option>
            {KNOWLEDGE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-4 py-2 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
          >
            <option value="">全部分类</option>
            {DEFAULT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {selectedIds.length > 0 && (
            <Button variant="outline" size="sm" onClick={handleBatchVectorize}>
              批量向量化 ({selectedIds.length})
            </Button>
          )}
        </div>

        {/* 表格 */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200/70 dark:border-white/10">
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium w-10 dark:text-white/50">
                  <input
                    type="checkbox"
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedIds(knowledge.map((k) => k.id));
                      } else {
                        setSelectedIds([]);
                      }
                    }}
                    checked={
                      selectedIds.length === knowledge.length &&
                      knowledge.length > 0
                    }
                    className="rounded"
                  />
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  标题
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  类型
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  分类
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  状态
                </th>
                <th className="text-left py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  向量化
                </th>
                <th className="text-right py-3 px-4 text-slate-500 text-sm font-medium dark:text-white/50">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {knowledge.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-slate-200/50 hover:bg-slate-50 dark:border-white/5 dark:hover:bg-white/5"
                >
                  <td className="py-4 px-4">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.id)}
                      onChange={() => toggleSelect(item.id)}
                      className="rounded"
                    />
                  </td>
                  <td className="py-4 px-4">
                    <div>
                      <p className="text-slate-900 font-medium truncate max-w-xs dark:text-white">
                        {item.title}
                      </p>
                      {item.article_number && (
                        <p className="text-slate-500 text-sm dark:text-white/40">
                          {item.article_number}
                        </p>
                      )}
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <Badge
                      variant={getTypeBadgeVariant(item.knowledge_type)}
                      size="sm"
                    >
                      {getTypeLabel(item.knowledge_type)}
                    </Badge>
                  </td>
                  <td className="py-4 px-4">
                    <Badge variant="info" size="sm">
                      {item.category}
                    </Badge>
                  </td>
                  <td className="py-4 px-4">
                    {item.is_active ? (
                      <Badge variant="success" size="sm">
                        启用
                      </Badge>
                    ) : (
                      <Badge variant="warning" size="sm">
                        禁用
                      </Badge>
                    )}
                  </td>
                  <td className="py-4 px-4">
                    {item.is_vectorized ? (
                      <Check className="h-5 w-5 text-green-400" />
                    ) : (
                      <span className="text-slate-400 dark:text-white/30">-</span>
                    )}
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2"
                        title="编辑"
                        onClick={() => openEditModal(item)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2 text-red-400 hover:text-red-300"
                        onClick={() => handleDelete(item.id)}
                        title="删除"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {knowledge.length === 0 && !loading && (
          <div className="text-center py-12 text-slate-500 dark:text-white/40">暂无知识条目</div>
        )}

        {total > pageSize && (
          <div className="mt-6">
            <Pagination
              currentPage={page}
              totalPages={Math.ceil(total / pageSize)}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>

      {/* 创建弹窗 */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          resetForm();
        }}
        title="添加知识"
        description="添加法律条文、案例或司法解释"
      >
        <KnowledgeForm
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleCreate}
          onCancel={() => {
            setShowCreateModal(false);
            resetForm();
          }}
          submitLabel="添加"
          submitLoading={createMutation.isPending}
        />
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingItem(null);
          resetForm();
        }}
        title="编辑知识"
        description="修改知识内容"
      >
        <KnowledgeForm
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleEdit}
          onCancel={() => {
            setShowEditModal(false);
            setEditingItem(null);
            resetForm();
          }}
          submitLabel="保存"
          submitLoading={editMutation.isPending}
        />
      </Modal>
    </div>
  );
}

// 表单组件
interface FormData {
  knowledge_type: KnowledgeType;
  title: string;
  article_number: string;
  content: string;
  summary: string;
  category: string;
  keywords: string;
  source: string;
  effective_date: string;
  weight: number;
  is_active: boolean;
}

interface KnowledgeFormProps {
  formData: FormData;
  setFormData: React.Dispatch<React.SetStateAction<FormData>>;
  onSubmit: () => void;
  onCancel: () => void;
  submitLabel: string;
  submitLoading: boolean;
}

function KnowledgeForm({
  formData,
  setFormData,
  onSubmit,
  onCancel,
  submitLabel,
  submitLoading,
}: KnowledgeFormProps) {
  return (
    <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
            类型
          </label>
          <select
            value={formData.knowledge_type}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                knowledge_type: e.target.value as KnowledgeType,
              }))
            }
            className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
          >
            {KNOWLEDGE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
            分类
          </label>
          <select
            value={formData.category}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, category: e.target.value }))
            }
            className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
          >
            {DEFAULT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Input
        label="标题"
        value={formData.title}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, title: e.target.value }))
        }
        placeholder="如：《中华人民共和国民法典》"
      />

      <Input
        label="条款编号（可选）"
        value={formData.article_number}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, article_number: e.target.value }))
        }
        placeholder="如：第一百二十条"
      />

      <Textarea
        label="内容"
        value={formData.content}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, content: e.target.value }))
        }
        placeholder="请输入法条内容或案例详情..."
        rows={6}
      />

      <Textarea
        label="摘要（可选）"
        value={formData.summary}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, summary: e.target.value }))
        }
        placeholder="简要概括要点..."
        rows={2}
      />

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="来源"
          value={formData.source}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, source: e.target.value }))
          }
          placeholder="如：全国人大常委会"
        />
        <Input
          label="生效日期"
          value={formData.effective_date}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, effective_date: e.target.value }))
          }
          placeholder="如：2021-01-01"
        />
      </div>

      <Input
        label="关键词（逗号分隔）"
        value={formData.keywords}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, keywords: e.target.value }))
        }
        placeholder="如：合同,违约,赔偿"
      />

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_active"
            checked={formData.is_active}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, is_active: e.target.checked }))
            }
            className="rounded"
          />
          <label htmlFor="is_active" className="text-sm text-slate-700 dark:text-white/70">
            启用
          </label>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-700 dark:text-white/70">权重：</label>
          <input
            type="number"
            min="0"
            max="10"
            step="0.1"
            value={formData.weight}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                weight: parseFloat(e.target.value) || 1,
              }))
            }
            className="w-20 px-3 py-1 rounded-lg border border-slate-200/70 bg-white text-slate-900 outline-none dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
          />
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-slate-200/70 dark:border-white/10">
        <Button variant="outline" onClick={onCancel}>
          取消
        </Button>
        <Button onClick={onSubmit} isLoading={submitLoading}>{submitLabel}</Button>
      </div>
    </div>
  );
}
