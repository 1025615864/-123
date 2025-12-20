import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  User,
  Mail,
  Phone,
  Camera,
  Save,
  Shield,
  MessageSquare,
  Heart,
  Star,
  Clock,
  Lock,
  Eye,
  EyeOff,
  Calendar,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  FileText,
  Edit,
  Trash2,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { useAppMutation, useToast } from "../hooks";
import { Card, Button, Input, Modal, Loading, EmptyState, FadeInImage, Pagination, Textarea } from "../components/ui";
import PageHeader from "../components/PageHeader";
import { useTheme } from "../contexts/ThemeContext";
import type { Post } from "../types";
import { getApiErrorMessage } from "../utils";

export default function ProfilePage() {
  const { user } = useAuth();
  const { actualTheme } = useTheme();
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const statsQueryKey = useMemo(() => ["user-me-stats", user?.id] as const, [user?.id]);
  const favoritesQueryKey = useMemo(() => ["forum-favorites", user?.id, { page: 1, page_size: 5 }] as const, [user?.id]);
  const myPostsQueryKey = useMemo(
    () => ["forum-me-posts", user?.id, { page: myPostsPage, page_size: myPostsPageSize }] as const,
    [myPostsPage, myPostsPageSize, user?.id]
  );

  const statsQuery = useQuery({
    queryKey: statsQueryKey,
    queryFn: async () => {
      const res = await api.get("/user/me/stats");
      return (res.data || { post_count: 0, favorite_count: 0, comment_count: 0 }) as {
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
      const res = await api.get("/forum/favorites", { params: { page: 1, page_size: 5 } });
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
  const myPostsTotalPages = Math.max(1, Math.ceil(myPostsTotal / myPostsPageSize));
  const myPostsError = myPostsQuery.isError ? getApiErrorMessage(myPostsQuery.error, "我的帖子加载失败") : null;
  const myPostsLoading = (myPostsQuery.isLoading || myPostsQuery.isFetching) && myPosts.length === 0;

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
  }, [statsQuery.data, statsQuery.error, statsQuery.isError, statsQuery.isFetching, statsQuery.isLoading]);

  useEffect(() => {
    setFavoritesLoading(favoritesQuery.isLoading || favoritesQuery.isFetching);
    if (favoritesQuery.isError) {
      setFavoritesError(getApiErrorMessage(favoritesQuery.error, "收藏内容加载失败"));
      setFavorites([]);
      return;
    }
    setFavoritesError(null);
    setFavorites(favoritesQuery.data ?? []);
  }, [favoritesQuery.data, favoritesQuery.error, favoritesQuery.isError, favoritesQuery.isFetching, favoritesQuery.isLoading]);

  const toggleFavoriteMutation = useAppMutation<{ favorited?: boolean }, number>({
    mutationFn: async (postId: number) => {
      const res = await api.post(`/forum/posts/${postId}/favorite`);
      return res.data as { favorited?: boolean };
    },
    errorMessageFallback: "操作失败，请稍后重试",
    onSuccess: (result, postId) => {
      if (result?.favorited === false) {
        queryClient.setQueryData<Post[]>(favoritesQueryKey as any, (old) => (Array.isArray(old) ? old.filter((p) => p.id !== postId) : old));
        queryClient.setQueryData(statsQueryKey as any, (old: any) => {
          if (!old) return old;
          return { ...old, favorite_count: Math.max(0, Number(old.favorite_count || 0) - 1) };
        });
        setFavorites((prev) => prev.filter((p) => p.id !== postId));
        setUserStats((prev) => ({
          ...prev,
          favorite_count: Math.max(0, (prev.favorite_count || 0) - 1),
        }));
        toast.success("已取消收藏");
      } else if (result?.favorited === true) {
        toast.success("收藏成功");
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

  const updateMyPostMutation = useAppMutation<Post, { id: number; title: string; content: string; category: string }>({
    mutationFn: async (payload) => {
      const res = await api.put(`/forum/posts/${payload.id}`,
        {
          title: payload.title,
          content: payload.content,
          category: payload.category,
        }
      );
      return res.data as Post;
    },
    successMessage: "更新成功",
    errorMessageFallback: "更新失败，请稍后重试",
    onSuccess: (updated) => {
      queryClient.setQueryData(myPostsQueryKey as any, (old: any) => {
        if (!old) return old;
        const nextItems = Array.isArray(old.items) ? old.items.map((p: Post) => (p.id === updated.id ? updated : p)) : old.items;
        return { ...old, items: nextItems };
      });
      closeEditPost();
    },
  });

  const deleteMyPostMutation = useAppMutation<void, number>({
    mutationFn: async (id) => {
      await api.delete(`/forum/posts/${id}`);
    },
    successMessage: "删除成功",
    errorMessageFallback: "删除失败，请稍后重试",
    onSuccess: (_, id) => {
      queryClient.setQueryData(myPostsQueryKey as any, (old: any) => {
        if (!old) return old;
        const nextItems = Array.isArray(old.items) ? old.items.filter((p: Post) => p.id !== id) : old.items;
        const nextTotal = Math.max(0, Number(old.total || 0) - 1);
        return { ...old, items: nextItems, total: nextTotal };
      });

      queryClient.setQueryData(statsQueryKey as any, (old: any) => {
        if (!old) return old;
        return { ...old, post_count: Math.max(0, Number(old.post_count || 0) - 1) };
      });
      setUserStats((prev) => ({
        ...prev,
        post_count: Math.max(0, (prev.post_count || 0) - 1),
      }));

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
    setMyPostsPage(1);
  }, [user?.id]);

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
      await api.put("/user/me", payload);
    },
    successMessage: "个人信息更新成功",
    errorMessageFallback: "更新失败，请稍后重试",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (updateProfileMutation.isPending) return;
    updateProfileMutation.mutate(formData);
  };

  const changePasswordMutation = useAppMutation<void, { old_password: string; new_password: string }>({
    mutationFn: async (payload) => {
      await api.put("/user/me/password", payload);
    },
    successMessage: "密码修改成功",
    errorMessageFallback: "密码修改失败，请稍后重试",
    onSuccess: () => {
      setShowPasswordModal(false);
      setPasswordForm({
        old_password: "",
        new_password: "",
        confirm_password: "",
      });
    },
  });

  // 密码修改处理
  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();

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
    { icon: Heart, label: "收藏内容", value: userStats.favorite_count, color: "text-pink-600 dark:text-pink-400" },
    { icon: Clock, label: "评论数", value: userStats.comment_count, color: "text-emerald-600 dark:text-green-400" },
  ];

  const postCategories = ["法律咨询", "经验分享", "案例讨论", "政策解读", "其他"];

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
          <h2 className="text-xl font-semibold text-slate-900 mb-2 dark:text-white">请先登录</h2>
          <p className="text-slate-600 dark:text-white/50">登录后即可查看和编辑个人信息</p>
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
              <p className="text-slate-600 text-sm mb-4 dark:text-white/50">@{user.username}</p>

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
                <div className="col-span-3">
                  <Loading text="加载中..." tone={actualTheme} />
                </div>
              ) : statsError ? (
                <div className="col-span-3 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                  <div>{statsError}</div>
                  <Button variant="outline" onClick={loadUserStats}>重试</Button>
                </div>
              ) : (
                stats.map(({ icon: Icon, label, value, color }) => (
                  <div key={label} className="text-center group cursor-pointer">
                    <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-slate-900/5 flex items-center justify-center group-hover:bg-slate-900/10 transition-colors dark:bg-white/5 dark:group-hover:bg-white/10">
                      <Icon className={`h-5 w-5 ${color}`} />
                    </div>
                    <p className="text-xl font-bold text-slate-900 dark:text-white">{value}</p>
                    <p className="text-xs text-slate-500 dark:text-white/40">{label}</p>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* 账户状态 */}
          <Card variant="surface" padding="md">
            <h4 className="text-sm font-medium text-slate-600 mb-4 dark:text-white/60">账户状态</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">邮箱验证</span>
                </div>
                <div className="flex items-center gap-1 text-green-400">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-xs">已验证</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">手机绑定</span>
                </div>
                {user.phone ? (
                  <div className="flex items-center gap-1 text-green-400">
                    <CheckCircle className="h-4 w-4" />
                    <span className="text-xs">已绑定</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                    <AlertCircle className="h-4 w-4" />
                    <span className="text-xs">未绑定</span>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-slate-400 dark:text-white/40" />
                  <span className="text-sm text-slate-700 dark:text-white/70">账户安全</span>
                </div>
                <div className="flex items-center gap-1 text-green-400">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-xs">正常</span>
                </div>
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
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">基本信息</h3>
                <p className="text-sm text-slate-600 dark:text-white/50">更新您的个人资料信息</p>
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
                />
                <Input
                  label="手机号"
                  icon={Phone}
                  value={formData.phone}
                  onChange={(e) =>
                    setFormData({ ...formData, phone: e.target.value })
                  }
                  placeholder="绑定手机号"
                  className="py-3"
                />
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  icon={Save}
                  isLoading={updateProfileMutation.isPending}
                  className="px-8"
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
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">安全设置</h3>
                <p className="text-sm text-slate-600 dark:text-white/50">管理您的账户安全选项</p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/5 border border-slate-200/70 dark:bg-white/[0.02] dark:border-white/5">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-slate-900 font-medium dark:text-white">登录密码</h4>
                  <p className="text-sm text-slate-600 mt-1 dark:text-white/50">
                    定期更换密码可以提高账户安全性
                  </p>
                </div>
                <Button
                  variant="secondary"
                  icon={Lock}
                  onClick={() => setShowPasswordModal(true)}
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
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">我的帖子</h3>
                  <p className="text-sm text-slate-600 dark:text-white/50">管理您发布的帖子内容</p>
                </div>
              </div>
              <Link
                to="/forum"
                className="text-amber-600 text-sm hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
              >
                去发布
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>

            {myPostsLoading ? (
              <Loading text="加载中..." tone={actualTheme} />
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
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-white/40">
                          <span>{post.category}</span>
                          <span>{new Date(post.created_at).toLocaleDateString()}</span>
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
                          <Button variant="ghost" size="sm" className="p-2" title="查看">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2"
                          title="编辑"
                          onClick={() => openEditPost(post)}
                          disabled={updateMyPostMutation.isPending || deleteMyPostMutation.isPending}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-2 text-red-500 hover:text-red-600 dark:text-red-300 dark:hover:text-red-200"
                          title="删除"
                          onClick={() => handleDeleteMyPost(post.id)}
                          disabled={deleteMyPostMutation.isPending || updateMyPostMutation.isPending}
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
                  <Link to="/forum">
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
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">我的收藏</h3>
                  <p className="text-sm text-slate-600 dark:text-white/50">您收藏的文章和帖子</p>
                </div>
              </div>
              <Link 
                to="/forum" 
                className="text-amber-600 text-sm hover:text-amber-700 flex items-center gap-1 dark:text-amber-400 dark:hover:text-amber-300"
              >
                查看全部
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>

            {favoritesLoading ? (
              <Loading text="加载中..." tone={actualTheme} />
            ) : favoritesError ? (
              <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                <div>{favoritesError}</div>
                <Button variant="outline" onClick={loadFavorites}>重试</Button>
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
                        <h4 className="text-slate-900 font-medium line-clamp-1 mb-2 dark:text-white">{post.title}</h4>
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
        isOpen={showEditPostModal}
        onClose={closeEditPost}
        title="编辑帖子"
        description="修改帖子标题、分类和内容"
        size="lg"
      >
        <form onSubmit={handleEditPostSubmit} className="space-y-5">
          <Input
            label="标题"
            value={editPostForm.title}
            onChange={(e) => setEditPostForm((prev) => ({ ...prev, title: e.target.value }))}
            placeholder="请输入标题"
            className="py-3"
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-white/70">分类</label>
            <select
              value={editPostForm.category}
              onChange={(e) => setEditPostForm((prev) => ({ ...prev, category: e.target.value }))}
              className="w-full px-4 py-3 rounded-xl border border-slate-200/70 bg-white text-slate-900 outline-none transition focus-visible:border-amber-500/50 focus-visible:ring-2 focus-visible:ring-amber-500/20 dark:border-white/10 dark:bg-[#0f0a1e]/60 dark:text-white"
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
            onChange={(e) => setEditPostForm((prev) => ({ ...prev, content: e.target.value }))}
            placeholder="请输入内容"
            className="min-h-[220px]"
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
            <Button type="submit" isLoading={updateMyPostMutation.isPending} className="flex-1">
              保存
            </Button>
          </div>
        </form>
      </Modal>

      {/* 密码修改弹窗 */}
      <Modal
        isOpen={showPasswordModal}
        onClose={() => {
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
            <label className="text-sm text-slate-700 dark:text-white/70">当前密码</label>
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
            <label className="text-sm text-slate-700 dark:text-white/70">新密码</label>
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
            <label className="text-sm text-slate-700 dark:text-white/70">确认新密码</label>
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
                setShowPasswordModal(false);
                setPasswordForm({
                  old_password: "",
                  new_password: "",
                  confirm_password: "",
                });
              }}
              className="flex-1"
            >
              取消
            </Button>
            <Button
              type="submit"
              isLoading={changePasswordMutation.isPending}
              className="flex-1"
            >
              确认修改
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
