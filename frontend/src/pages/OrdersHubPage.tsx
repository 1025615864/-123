import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Calendar, FileText } from "lucide-react";
import PageHeader from "../components/PageHeader";
import { Button } from "../components/ui";
import { useTheme } from "../contexts/ThemeContext";
import OrdersPage from "./OrdersPage";
import LawFirmConsultationsPage from "./LawFirmConsultationsPage";

type OrdersTab = "payment" | "consultations";

function normalizeTab(value: string | null | undefined): OrdersTab {
  const v = String(value ?? "")
    .trim()
    .toLowerCase();
  if (v === "consultations" || v === "consultation") return "consultations";
  return "payment";
}

export default function OrdersHubPage() {
  const { actualTheme } = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();

  const tab = useMemo(
    () => normalizeTab(searchParams.get("tab")),
    [searchParams]
  );

  const setTab = (next: OrdersTab) => {
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.set("tab", next);
        return p;
      },
      { replace: true }
    );
  };

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="订单"
        title="我的订单 / 我的预约"
        description="统一管理支付订单与律师预约"
        layout="mdStart"
        tone={actualTheme}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={tab === "payment" ? "primary" : "outline"}
          size="sm"
          icon={FileText}
          onClick={() => setTab("payment")}
        >
          支付订单
        </Button>
        <Button
          variant={tab === "consultations" ? "primary" : "outline"}
          size="sm"
          icon={Calendar}
          onClick={() => setTab("consultations")}
        >
          律师预约
        </Button>
      </div>

      {tab === "consultations" ? (
        <LawFirmConsultationsPage embedded />
      ) : (
        <OrdersPage embedded />
      )}
    </div>
  );
}
