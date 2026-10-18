import {
  BarChart3,
  ChartLine,
  ChartPie,
  LayoutDashboard,
  Package,
  ShoppingCart,
  Stethoscope,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

/** Catalogue icon names (app.dashboard.icon) → components. Unknown names fall back. */
const ICONS: Record<string, LucideIcon> = {
  "chart-line": ChartLine,
  "chart-pie": ChartPie,
  "bar-chart": BarChart3,
  package: Package,
  "shopping-cart": ShoppingCart,
  stethoscope: Stethoscope,
  users: Users,
  wallet: Wallet,
};

export function dashboardIcon(name: string): LucideIcon {
  return ICONS[name] ?? LayoutDashboard;
}
