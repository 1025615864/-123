export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  nickname?: string;
  avatar?: string;
  phone?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface Author {
  id: number;
  username: string;
  nickname?: string;
  avatar?: string;
}

export interface Post {
  id: number;
  title: string;
  content: string;
  category: string;
  user_id?: number;
  author?: Author;
  view_count?: number;
  like_count: number;
  comment_count: number;
  share_count?: number;
  favorite_count?: number;
  is_liked?: boolean;
  is_favorited?: boolean;
  is_pinned?: boolean;
  is_hot?: boolean;
  is_essence?: boolean;
  heat_score?: number;
  cover_image?: string;
  images?: string[];
  attachments?: Array<{ name: string; url: string }>;
  reactions?: Array<{ emoji: string; count: number }>;
  created_at: string;
  updated_at?: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface NewsItem {
  id: number;
  title: string;
  summary: string;
  content: string;
  category: string;
  source: string;
  published_at: string;
  created_at: string;
}

export interface LawFirm {
  id: number;
  name: string;
  address: string;
  phone: string;
  email: string;
  description: string;
  rating: number;
  specialties: string[];
}

export interface ApiError {
  detail?: string;
  message?: string;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

// 通知类型
export interface Notification {
  id: number;
  user_id: number;
  type: string;
  title: string;
  content: string;
  is_read: boolean;
  related_id?: number;
  related_type?: string;
  created_at: string;
}

// 评论类型
export interface Comment {
  id: number;
  post_id: number;
  user_id: number;
  content: string;
  author?: Author;
  like_count?: number;
  is_liked?: boolean;
  created_at: string;
}

// 律师类型
export interface Lawyer {
  id: number;
  name: string;
  title: string;
  specialty: string[];
  experience_years: number;
  rating: number;
  avatar?: string;
  firm_id: number;
  firm_name?: string;
}

// 支付订单
export interface PaymentOrder {
  id: number;
  order_no: string;
  order_type: string;
  amount: number;
  actual_amount: number;
  status: string;
  payment_method?: string;
  title: string;
  created_at: string;
  paid_at?: string;
}

// 用户余额
export interface UserBalance {
  balance: number;
  frozen: number;
  total_recharged: number;
  total_consumed: number;
}

// 知识库
export interface LegalKnowledge {
  id: number;
  title: string;
  content: string;
  category_id?: number;
  category_name?: string;
  keywords?: string[];
  view_count?: number;
  created_at: string;
}
