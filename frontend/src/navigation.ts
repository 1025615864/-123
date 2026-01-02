import {
  Home,
  MessageCircle,
  Newspaper,
  Building2,
  MessageSquare,
  User,
  Calculator,
  Clock,
  Calendar,
  FileText,
  HelpCircle,
} from "lucide-react";

export interface NavItem {
  path: string;
  label: string;
  icon: typeof Home;
}

export const primaryNavItems: NavItem[] = [
  { path: "/", label: "首页", icon: Home },
  { path: "/chat", label: "AI咨询", icon: MessageCircle },
  { path: "/news", label: "新闻解读", icon: Newspaper },
  { path: "/lawfirm", label: "找律所", icon: Building2 },
  { path: "/forum", label: "法律论坛", icon: MessageSquare },
  { path: "/profile", label: "个人中心", icon: User },
];

export const toolNavItems: NavItem[] = [
  { path: "/calculator", label: "费用计算", icon: Calculator },
  { path: "/limitations", label: "时效计算", icon: Clock },
  { path: "/documents", label: "文书生成", icon: FileText },
  { path: "/calendar", label: "法律日历", icon: Calendar },
];

export const secondaryNavItems: NavItem[] = [
  { path: "/faq", label: "FAQ", icon: HelpCircle },
];

export function isRouteActive(currentPath: string, itemPath: string): boolean {
  if (itemPath === "/") return currentPath === "/";
  return currentPath === itemPath || currentPath.startsWith(itemPath + "/");
}
