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
  { path: "/", label: "nav.home", icon: Home },
  { path: "/chat", label: "nav.consultation", icon: MessageCircle },
  { path: "/news", label: "nav.news", icon: Newspaper },
  { path: "/lawfirm", label: "nav.lawfirm", icon: Building2 },
  { path: "/forum", label: "nav.forum", icon: MessageSquare },
  { path: "/profile", label: "nav.profile", icon: User },
];

export const toolNavItems: NavItem[] = [
  { path: "/calculator", label: "tool.feeCalculator", icon: Calculator },
  { path: "/limitations", label: "tool.limitationsCalculator", icon: Clock },
  { path: "/documents", label: "tool.documentGenerator", icon: FileText },
  { path: "/contracts", label: "tool.contractReview", icon: FileText },
  { path: "/calendar", label: "tool.calendar", icon: Calendar },
];

export const secondaryNavItems: NavItem[] = [
  { path: "/faq", label: "nav.faq", icon: HelpCircle },
];

export function isRouteActive(currentPath: string, itemPath: string): boolean {
  if (itemPath === "/") return currentPath === "/";
  return currentPath === itemPath || currentPath.startsWith(itemPath + "/");
}
