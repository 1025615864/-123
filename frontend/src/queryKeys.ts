export const queryKeys = {
  notifications: (page: number, pageSize: number) =>
    ["notifications", { page, pageSize }] as const,
  notificationsPreview: (pageSize: number = 10) =>
    ["notifications-preview", { pageSize }] as const,
  adminSystemNotifications: () => ["admin-system-notifications"] as const,
  aiConsultations: () => ["ai-consultations"] as const,
  adminDashboardStats: () => ["admin-dashboard-stats"] as const,
  adminDashboardTrends: (days: number) =>
    ["admin-dashboard-trends", { days }] as const,
  adminDashboardCategoryStats: () =>
    ["admin-dashboard-category-stats"] as const,
  adminDashboardRealtime: () => ["admin-dashboard-realtime"] as const,
  adminDashboardHot: (limit: number) =>
    ["admin-dashboard-hot", { limit }] as const,
  adminDashboardNewsStats: (days: number, limit: number) =>
    ["admin-dashboard-news-stats", { days, limit }] as const,

  lawFirms: (keyword: string, city: string) =>
    ["lawfirms", { keyword, city }] as const,
  lawFirm: (firmId: string | undefined) => ["lawfirm", { firmId }] as const,
  lawFirmLawyers: (firmId: string | undefined) =>
    ["lawfirm-lawyers", { firmId }] as const,

  newsCategories: () => ["news-categories"] as const,
  newsList: (
    page: number,
    pageSize: number,
    category: string | null,
    keyword: string
  ) => ["news", { page, pageSize, category, keyword }] as const,
  newsFavoritesList: (
    page: number,
    pageSize: number,
    category: string | null,
    keyword: string
  ) => ["news-favorites", { page, pageSize, category, keyword }] as const,
  newsHistoryList: (
    page: number,
    pageSize: number,
    category: string | null,
    keyword: string
  ) => ["news-history", { page, pageSize, category, keyword }] as const,
  newsTop: (limit: number) => ["news-top", { limit }] as const,
  newsRecent: (limit: number) => ["news-recent", { limit }] as const,
  newsHot: (days: number, limit: number, category: string | null = null) =>
    ["news-hot", { days, limit, category }] as const,
  newsDetail: (newsId: string | undefined) => ["news", newsId] as const,
  newsRelated: (newsId: string | undefined, limit: number) =>
    ["news-related", { newsId, limit }] as const,
  newsSubscriptions: () => ["news-subscriptions"] as const,

  documentTypes: () => ["document-types"] as const,

  systemConfigs: () => ["system-configs"] as const,

  forumPost: (postId: string | undefined) => ["forum-post", postId] as const,
  forumPostComments: (postId: string | undefined) =>
    ["forum-post-comments", postId] as const,
  forumMyComments: (page: number, pageSize: number, status: string) =>
    ["forum-my-comments", { page, pageSize, status }] as const,
  forumPostsRoot: () => ["forum-posts"] as const,
  forumHotPosts: (limit: number, category: string | null) =>
    ["forum-hot-posts", { limit, category }] as const,
  forumPosts: (
    page: number,
    pageSize: number,
    activeCategory: string,
    keyword: string,
    favorites: boolean
  ) =>
    [
      "forum-posts",
      {
        page,
        pageSize,
        activeCategory,
        keyword,
        favorites,
      },
    ] as const,

  forumStats: () => ["forum-stats"] as const,
  adminForumPosts: (
    page: number,
    pageSize: number,
    keyword: string,
    category: string,
    deleted: boolean
  ) =>
    [
      "admin-forum-posts",
      { page, pageSize, keyword, category, deleted },
    ] as const,
  adminForumPendingComments: (page: number, pageSize: number) =>
    ["admin-forum-pending-comments", { page, pageSize }] as const,
  adminForumPendingPosts: (page: number, pageSize: number) =>
    ["admin-forum-pending-posts", { page, pageSize }] as const,
  adminForumContentStats: () => ["admin-forum-content-stats"] as const,
  adminForumWords: () => ["admin-forum-words"] as const,
  adminForumPostReviewConfig: () => ["admin-forum-post-review-config"] as const,
  adminForumContentFilterConfig: () =>
    ["admin-forum-content-filter-config"] as const,

  knowledgeTemplates: (isActive: boolean) =>
    ["knowledge-templates", { is_active: isActive }] as const,

  knowledgeStats: () => ["knowledge-stats"] as const,
  adminKnowledgeListRoot: () => ["admin-knowledge-list"] as const,
  adminKnowledgeList: (
    page: number,
    pageSize: number,
    keyword: string,
    knowledgeType: string,
    category: string
  ) =>
    [
      "admin-knowledge-list",
      {
        page,
        pageSize,
        keyword,
        knowledge_type: knowledgeType,
        category,
      },
    ] as const,

  searchHot: (limit: number) => ["search-hot", { limit }] as const,
  searchHistoryRoot: () => ["search-history"] as const,
  searchHistory: (limit: number) => ["search-history", { limit }] as const,
  searchSuggestions: (q: string, limit: number) =>
    ["search-suggestions", { q, limit }] as const,
  search: (q: string, limit: number) => ["search", { q, limit }] as const,

  adminUsers: (page: number, pageSize: number, keyword: string) =>
    ["admin-users", { page, pageSize, keyword }] as const,
  adminUserStats: (userId: number | undefined) =>
    ["admin-user-stats", userId] as const,
};
