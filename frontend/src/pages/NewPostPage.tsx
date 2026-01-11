import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Eye, FileText, Send } from "lucide-react";

import { Button, Card, Input, ListSkeleton, Textarea } from "../components/ui";
import RichTextEditor from "../components/RichTextEditor";
import MarkdownContent from "../components/MarkdownContent";
import PageHeader from "../components/PageHeader";

import api from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage, storage } from "../utils";
import { queryKeys } from "../queryKeys";

const DRAFTS_KEY = "forum:postDrafts";
const LEGACY_DRAFT_KEY = "forum:newPostDraft";

type Attachment = { name: string; url: string };

type StructuredFields = {
  facts: string;
  issues: string;
  evidence: string;
  claims: string;
  progress: string;
};

interface DraftPayload {
  id: string;
  title: string;
  category: string;
  content: string;
  images: string[];
  attachments: Attachment[];
  structured_enabled?: boolean;
  structured?: StructuredFields;
  createdAt: number;
  updatedAt: number;
}

function safeArray<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}

function createDraftId() {
  return `${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function upsertSection(base: string, heading: string, body: string): string {
  const src = String(base ?? "");
  const h = String(heading ?? "").trim();
  const safeBody = String(body ?? "").trim();
  if (!h) return src;

  const normalized = src.replace(/\r\n/g, "\n");
  const headingRe = new RegExp(`^##\\s+${escapeRegExp(h)}\\s*$`, "m");
  const m = normalized.match(headingRe);
  const nextChunk = `\n\n## ${h}\n\n${safeBody}\n`;

  if (!m || typeof m.index !== "number") {
    if (!normalized.trim()) return nextChunk.trim() + "\n";
    return normalized.trimEnd() + nextChunk;
  }

  const idx = m.index;
  const afterHeading = normalized.indexOf("\n", idx);
  const start = afterHeading === -1 ? normalized.length : afterHeading + 1;

  const rest = normalized.slice(start);
  const nextHeadingRe = /^##\s+.+$/m;
  const nextMatch = rest.match(nextHeadingRe);
  const end = nextMatch && typeof nextMatch.index === "number" ? start + nextMatch.index : normalized.length;

  const prefix = normalized.slice(0, start);
  const suffix = normalized.slice(end);
  const injected = `\n${safeBody}\n`;

  return (prefix.trimEnd() + injected + suffix.trimStart()).trim() + "\n";
}

function buildStructuredMarkdown(fields: StructuredFields): string {
  const facts = String(fields.facts || "").trim() || "（请填写：时间、地点、人物、经过）";
  const issues = String(fields.issues || "").trim() || "（请填写：核心争议点/你最关心的问题）";
  const evidence = String(fields.evidence || "").trim() || "（请填写：聊天记录、转账记录、合同、录音等）";
  const claims = String(fields.claims || "").trim() || "（请填写：希望达到的结果/诉求）";
  const progress = String(fields.progress || "").trim() || "（请填写：目前进展、关键时间点、是否已协商/报警/起诉等）";

  return (
    `## 案情经过\n\n${facts}\n\n` +
    `## 争议焦点\n\n${issues}\n\n` +
    `## 证据线索\n\n${evidence}\n\n` +
    `## 诉求/目标\n\n${claims}\n\n` +
    `## 进展与时间线\n\n${progress}\n`
  );
}

function hasStructuredAny(fields: StructuredFields): boolean {
  return Boolean(
    String(fields.facts || "").trim() ||
      String(fields.issues || "").trim() ||
      String(fields.evidence || "").trim() ||
      String(fields.claims || "").trim() ||
      String(fields.progress || "").trim()
  );
}

export default function NewPostPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const { isAuthenticated } = useAuth();
  const { actualTheme } = useTheme();

  const draftParam = searchParams.get("draft");

  const [draftId, setDraftId] = useState<string | null>(null);
  const [draftCreatedAt, setDraftCreatedAt] = useState<number>(Date.now());

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("法律咨询");
  const [content, setContent] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [preview, setPreview] = useState(false);

  const [structuredEnabled, setStructuredEnabled] = useState(false);
  const [caseFacts, setCaseFacts] = useState("");
  const [caseIssues, setCaseIssues] = useState("");
  const [caseEvidence, setCaseEvidence] = useState("");
  const [caseClaims, setCaseClaims] = useState("");
  const [caseProgress, setCaseProgress] = useState("");
  const [hydrated, setHydrated] = useState(false);

  const [draftSaving, setDraftSaving] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [draftLastSavedAt, setDraftLastSavedAt] = useState<number | null>(null);

  const postCategories = useMemo(
    () => ["法律咨询", "经验分享", "案例讨论", "政策解读", "其他"],
    []
  );

  useEffect(() => {
    const raw = storage.get<unknown>(DRAFTS_KEY, []);
    const drafts = safeArray<DraftPayload>(raw);

    if (draftParam) {
      const existing = drafts.find((d) => d && d.id === draftParam);
      if (existing) {
        setDraftId(existing.id);
        setDraftCreatedAt(existing.createdAt || Date.now());
        setTitle(existing.title || "");
        setCategory(existing.category || "法律咨询");
        setContent(existing.content || "");
        setImages(Array.isArray(existing.images) ? existing.images : []);
        setAttachments(
          Array.isArray(existing.attachments) ? existing.attachments : []
        );
        setStructuredEnabled(Boolean((existing as any)?.structured_enabled));
        const structured = (existing as any)?.structured;
        if (structured && typeof structured === "object") {
          setCaseFacts(String((structured as any).facts ?? ""));
          setCaseIssues(String((structured as any).issues ?? ""));
          setCaseEvidence(String((structured as any).evidence ?? ""));
          setCaseClaims(String((structured as any).claims ?? ""));
          setCaseProgress(String((structured as any).progress ?? ""));
        }
        setDraftLastSavedAt(
          Number(existing.updatedAt || existing.createdAt || Date.now())
        );
        setDraftDirty(false);
        setHydrated(true);
        return;
      }
    }

    const legacy =
      storage.get<Omit<DraftPayload, "id" | "createdAt">>(LEGACY_DRAFT_KEY);
    if (
      legacy &&
      (legacy.title ||
        legacy.content ||
        (legacy.images?.length ?? 0) > 0 ||
        (legacy.attachments?.length ?? 0) > 0)
    ) {
      const id = createDraftId();
      const now = Date.now();
      const payload: DraftPayload = {
        id,
        title: legacy.title || "",
        category: legacy.category || "法律咨询",
        content: legacy.content || "",
        images: Array.isArray(legacy.images) ? legacy.images : [],
        attachments: Array.isArray(legacy.attachments)
          ? legacy.attachments
          : [],
        createdAt: now,
        updatedAt: legacy.updatedAt || now,
      };
      storage.remove(LEGACY_DRAFT_KEY);
      storage.set(DRAFTS_KEY, [payload, ...drafts]);
      setDraftId(id);
      setDraftCreatedAt(payload.createdAt);
      setTitle(payload.title);
      setCategory(payload.category);
      setContent(payload.content);
      setImages(payload.images);
      setAttachments(payload.attachments);
      setStructuredEnabled(Boolean((payload as any)?.structured_enabled));
      const structured = (payload as any)?.structured;
      if (structured && typeof structured === "object") {
        setCaseFacts(String((structured as any).facts ?? ""));
        setCaseIssues(String((structured as any).issues ?? ""));
        setCaseEvidence(String((structured as any).evidence ?? ""));
        setCaseClaims(String((structured as any).claims ?? ""));
        setCaseProgress(String((structured as any).progress ?? ""));
      }
      setDraftLastSavedAt(
        Number(payload.updatedAt || payload.createdAt || Date.now())
      );
      setDraftDirty(false);
      setHydrated(true);
      return;
    }

    const id = createDraftId();
    setDraftId(id);
    setDraftCreatedAt(Date.now());
    setTitle("");
    setCategory("法律咨询");
    setContent("");
    setImages([]);
    setAttachments([]);
    setStructuredEnabled(false);
    setCaseFacts("");
    setCaseIssues("");
    setCaseEvidence("");
    setCaseClaims("");
    setCaseProgress("");
    setPreview(false);
    setDraftLastSavedAt(null);
    setDraftDirty(false);
    setHydrated(true);
  }, [draftParam]);

  const handleTitleChange = (v: string) => {
    setTitle(v);
    setDraftDirty(true);
  };

  const handleCategoryChange = (v: string) => {
    setCategory(v);
    setDraftDirty(true);
  };

  const handleContentChange = (v: string) => {
    setContent(v);
    setDraftDirty(true);
  };

  const currentStructuredFields: StructuredFields = useMemo(
    () => ({
      facts: caseFacts,
      issues: caseIssues,
      evidence: caseEvidence,
      claims: caseClaims,
      progress: caseProgress,
    }),
    [caseEvidence, caseFacts, caseIssues, caseClaims, caseProgress]
  );

  const syncStructuredToContent = (mode: "merge" | "replace" | "append") => {
    if (!structuredEnabled) {
      toast.info("请先开启结构化模板");
      return;
    }
    const hasAny = hasStructuredAny(currentStructuredFields);
    const template = buildStructuredMarkdown(currentStructuredFields);
    if (!hasAny && mode !== "replace") {
      toast.info("模板字段为空");
      return;
    }

    if (mode === "replace") {
      setContent(template);
      setDraftDirty(true);
      toast.success("已生成模板到正文");
      return;
    }

    if (mode === "append") {
      const next = (String(content || "").trimEnd() + "\n\n" + template).trim() + "\n";
      setContent(next);
      setDraftDirty(true);
      toast.success("已插入模板到正文");
      return;
    }

    let next = String(content || "");
    next = upsertSection(next, "案情经过", String(currentStructuredFields.facts || "").trim() || "（请填写：时间、地点、人物、经过）");
    next = upsertSection(next, "争议焦点", String(currentStructuredFields.issues || "").trim() || "（请填写：核心争议点/你最关心的问题）");
    next = upsertSection(next, "证据线索", String(currentStructuredFields.evidence || "").trim() || "（请填写：聊天记录、转账记录、合同、录音等）");
    next = upsertSection(next, "诉求/目标", String(currentStructuredFields.claims || "").trim() || "（请填写：希望达到的结果/诉求）");
    next = upsertSection(next, "进展与时间线", String(currentStructuredFields.progress || "").trim() || "（请填写：目前进展、关键时间点、是否已协商/报警/起诉等）");
    setContent(next);
    setDraftDirty(true);
    toast.success("已同步到正文");
  };

  const handleImagesChange = (v: string[]) => {
    setImages(v);
    setDraftDirty(true);
  };

  const handleAttachmentsChange = (v: Attachment[]) => {
    setAttachments(v);
    setDraftDirty(true);
  };

  const draftStatusText = useMemo(() => {
    if (!hydrated || !draftId) return "";
    if (draftSaving) return "保存中...";
    if (draftDirty) return "未保存（将自动保存）";
    if (draftLastSavedAt)
      return `已保存 ${new Date(draftLastSavedAt).toLocaleTimeString()}`;
    return "已自动保存（本地）";
  }, [draftDirty, draftId, draftLastSavedAt, draftSaving, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    if (!draftId) return;
    const timer = window.setTimeout(() => {
      const isEmpty =
        !title.trim() &&
        !content.trim() &&
        !hasStructuredAny(currentStructuredFields) &&
        (images?.length ?? 0) === 0 &&
        (attachments?.length ?? 0) === 0;

      const payload: DraftPayload = {
        id: draftId,
        title,
        category,
        content,
        images,
        attachments,
        structured_enabled: structuredEnabled,
        structured: currentStructuredFields,
        createdAt: draftCreatedAt,
        updatedAt: Date.now(),
      };

      const raw = storage.get<unknown>(DRAFTS_KEY, []);
      const drafts = safeArray<DraftPayload>(raw);
      const idx = drafts.findIndex((d) => d && d.id === draftId);

      if (isEmpty) {
        if (idx >= 0) {
          try {
            setDraftSaving(true);
            storage.set(
              DRAFTS_KEY,
              drafts.filter((d) => d && d.id !== draftId)
            );
            setDraftLastSavedAt(Date.now());
            setDraftDirty(false);
          } catch (err) {
            toast.error("草稿保存失败，请稍后重试");
          } finally {
            setDraftSaving(false);
          }
        }
        return;
      }

      const next = [...drafts];
      if (idx >= 0) {
        next[idx] = payload;
      } else {
        next.unshift(payload);
      }
      try {
        setDraftSaving(true);
        storage.set(DRAFTS_KEY, next);
        setDraftLastSavedAt(payload.updatedAt);
        setDraftDirty(false);
      } catch (err) {
        toast.error("草稿保存失败，请稍后重试");
      } finally {
        setDraftSaving(false);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [
    title,
    category,
    content,
    images,
    attachments,
    structuredEnabled,
    currentStructuredFields,
    hydrated,
    draftId,
    draftCreatedAt,
    toast,
  ]);

  const clearDraft = () => {
    if (draftId) {
      const raw = storage.get<unknown>(DRAFTS_KEY, []);
      const drafts = safeArray<DraftPayload>(raw);
      storage.set(
        DRAFTS_KEY,
        drafts.filter((d) => d && d.id !== draftId)
      );
    }
    setTitle("");
    setCategory("法律咨询");
    setContent("");
    setImages([]);
    setAttachments([]);
    setStructuredEnabled(false);
    setCaseFacts("");
    setCaseIssues("");
    setCaseEvidence("");
    setCaseClaims("");
    setCaseProgress("");
    const nextId = createDraftId();
    setDraftId(nextId);
    setDraftCreatedAt(Date.now());
    setDraftLastSavedAt(null);
    setDraftDirty(false);
    navigate("/forum/new", { replace: true });
    toast.success("草稿已清空");
  };

  const publishMutation = useAppMutation<
    { id: number; review_status?: string | null },
    { content: string }
  >({
    mutationFn: async ({ content: finalContent }) => {
      const res = await api.post("/forum/posts", {
        title,
        category,
        content: finalContent,
        images,
        attachments,
      });
      return res.data as { id: number; review_status?: string | null };
    },
    errorMessageFallback: "发布失败，请稍后重试",
    invalidateQueryKeys: [queryKeys.forumPostsRoot()],
    onSuccess: (data) => {
      if (draftId) {
        const raw = storage.get<unknown>(DRAFTS_KEY, []);
        const drafts = safeArray<DraftPayload>(raw);
        storage.set(
          DRAFTS_KEY,
          drafts.filter((d) => d && d.id !== draftId)
        );
      }
      toast.success("发布成功");
      if (data?.review_status === "pending") {
        toast.info("帖子已提交审核，通过后将展示");
      }
      const id = (data as any)?.id;
      if (id) {
        navigate(`/forum/post/${id}`);
        return;
      }
      navigate("/forum");
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, "发布失败，请稍后重试"));
    },
  });

  const publishBusy = publishMutation.isPending;

  const handlePublish = () => {
    if (!isAuthenticated) {
      toast.error("请先登录后再发帖");
      navigate("/login");
      return;
    }
    if (!title.trim()) {
      toast.error("请填写标题");
      return;
    }
    const finalContent =
      structuredEnabled && hasStructuredAny(currentStructuredFields)
        ? (() => {
            let next = String(content || "");
            if (!next.trim()) {
              return buildStructuredMarkdown(currentStructuredFields);
            }
            next = upsertSection(next, "案情经过", String(currentStructuredFields.facts || "").trim() || "（请填写：时间、地点、人物、经过）");
            next = upsertSection(next, "争议焦点", String(currentStructuredFields.issues || "").trim() || "（请填写：核心争议点/你最关心的问题）");
            next = upsertSection(next, "证据线索", String(currentStructuredFields.evidence || "").trim() || "（请填写：聊天记录、转账记录、合同、录音等）");
            next = upsertSection(next, "诉求/目标", String(currentStructuredFields.claims || "").trim() || "（请填写：希望达到的结果/诉求）");
            next = upsertSection(next, "进展与时间线", String(currentStructuredFields.progress || "").trim() || "（请填写：目前进展、关键时间点、是否已协商/报警/起诉等）");
            return next;
          })()
        : String(content || "");

    if (!finalContent.trim()) {
      toast.error("请填写内容");
      return;
    }
    if (publishBusy) return;
    if (finalContent !== content) {
      setContent(finalContent);
      setDraftDirty(true);
    }
    publishMutation.mutate({ content: finalContent });
  };

  if (!hydrated) {
    return (
      <div className="space-y-8">
        <ListSkeleton count={4} />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Link
        to="/forum"
        onClick={(e) => {
          if (publishBusy) e.preventDefault();
        }}
        aria-disabled={publishBusy}
        className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        返回论坛
      </Link>

      <PageHeader
        eyebrow="社区交流"
        title="发布帖子"
        description="支持图片内嵌、附件插入，并自动保存草稿"
        tone={actualTheme}
        layout="mdCenter"
        right={
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center text-xs text-slate-500 px-2 dark:text-white/45">
              {draftStatusText}
            </div>
            <Button
              variant={preview ? "secondary" : "outline"}
              icon={Eye}
              onClick={() => {
                if (publishBusy) return;
                if (!preview && structuredEnabled && hasStructuredAny(currentStructuredFields)) {
                  syncStructuredToContent(content.trim() ? "merge" : "replace");
                }
                setPreview((p) => !p);
              }}
              disabled={publishBusy}
            >
              {preview ? "编辑" : "预览"}
            </Button>
            <Button
              variant="outline"
              icon={FileText}
              onClick={() => {
                if (publishBusy) return;
                navigate("/forum/drafts");
              }}
              disabled={publishBusy}
            >
              草稿箱
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                if (publishBusy) return;
                clearDraft();
              }}
              disabled={publishBusy}
            >
              清空草稿
            </Button>
            <Button
              icon={Send}
              onClick={handlePublish}
              isLoading={publishBusy}
              loadingText="发布中..."
              disabled={publishBusy}
            >
              发布
            </Button>
          </div>
        }
      />

      <Card variant="surface" padding="lg">
        <div className={`space-y-5 ${publishBusy ? "opacity-60 pointer-events-none" : ""}`}>
          <Input
            label="标题"
            value={title}
            onChange={(e) => handleTitleChange(e.target.value)}
            placeholder="请用一句话描述你的问题/观点"
            disabled={publishBusy}
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
              分类
            </label>
            <select
              value={category}
              onChange={(e) => handleCategoryChange(e.target.value)}
              disabled={publishBusy}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition hover:border-slate-300 focus-visible:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-900"
            >
              {postCategories.map((cat) => (
                <option
                  key={cat}
                  value={cat}
                  className="bg-white text-slate-900 dark:bg-[#0f0a1e] dark:text-white"
                >
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-2xl border border-slate-200/70 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  结构化发帖模板
                </div>
                <div className="text-xs text-slate-500 mt-1 dark:text-white/45">
                  按案情要素组织内容，便于他人快速理解并回复
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant={structuredEnabled ? "secondary" : "outline"}
                  onClick={() => {
                    setStructuredEnabled((v) => !v);
                    setDraftDirty(true);
                  }}
                  disabled={publishBusy}
                >
                  {structuredEnabled ? "已开启" : "开启"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (publishBusy) return;
                    syncStructuredToContent(content.trim() ? "merge" : "replace");
                  }}
                  disabled={publishBusy || !structuredEnabled}
                >
                  同步到正文
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (publishBusy) return;
                    syncStructuredToContent("append");
                  }}
                  disabled={publishBusy || !structuredEnabled}
                >
                  插入模板
                </Button>
              </div>
            </div>

            {structuredEnabled ? (
              <div className="mt-4 grid grid-cols-1 gap-4">
                <Textarea
                  label="案情经过"
                  value={caseFacts}
                  onChange={(e) => {
                    setCaseFacts(e.target.value);
                    setDraftDirty(true);
                  }}
                  rows={4}
                  placeholder="时间、地点、人物、经过..."
                  disabled={publishBusy}
                />
                <Textarea
                  label="争议焦点"
                  value={caseIssues}
                  onChange={(e) => {
                    setCaseIssues(e.target.value);
                    setDraftDirty(true);
                  }}
                  rows={3}
                  placeholder="你最想解决的问题/争议点..."
                  disabled={publishBusy}
                />
                <Textarea
                  label="证据线索"
                  value={caseEvidence}
                  onChange={(e) => {
                    setCaseEvidence(e.target.value);
                    setDraftDirty(true);
                  }}
                  rows={3}
                  placeholder="合同、聊天记录、转账记录、录音、证人..."
                  disabled={publishBusy}
                />
                <Textarea
                  label="诉求/目标"
                  value={caseClaims}
                  onChange={(e) => {
                    setCaseClaims(e.target.value);
                    setDraftDirty(true);
                  }}
                  rows={3}
                  placeholder="希望对方做什么/你希望达到的结果..."
                  disabled={publishBusy}
                />
                <Textarea
                  label="进展与时间线"
                  value={caseProgress}
                  onChange={(e) => {
                    setCaseProgress(e.target.value);
                    setDraftDirty(true);
                  }}
                  rows={3}
                  placeholder="目前进展、关键时间点、是否协商/报警/起诉..."
                  disabled={publishBusy}
                />
              </div>
            ) : null}
          </div>

          {preview ? (
            <div className="rounded-2xl border border-slate-200/70 bg-white p-5 dark:border-white/10 dark:bg-[#0f0a1e]/60">
              <MarkdownContent content={content || "（暂无内容）"} />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">
                内容
              </label>
              <RichTextEditor
                value={content}
                onChange={handleContentChange}
                images={images}
                onImagesChange={handleImagesChange}
                attachments={attachments}
                onAttachmentsChange={handleAttachmentsChange}
                placeholder="请输入内容，支持 Markdown、表情、图片和附件链接..."
                minHeight="260px"
              />
              <p className="text-xs text-slate-500 mt-2 dark:text-white/40">
                {draftStatusText}。图片会以 Markdown 形式插入到正文中。
              </p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
