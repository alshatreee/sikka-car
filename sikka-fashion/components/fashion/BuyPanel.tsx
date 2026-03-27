"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import { ShoppingBag, Shield, TrendingDown } from "lucide-react";
import { MockFashionItem } from "@/lib/mockData";

interface BuyPanelProps {
  item: MockFashionItem;
}

export default function BuyPanel({ item }: BuyPanelProps) {
  const { t } = useLanguage();

  const savings = item.retailPrice - (item.salePrice || 0);
  const savingsPercent = Math.round((savings / item.retailPrice) * 100);
  const serviceFee = Math.round((item.salePrice || 0) * 0.05 * 100) / 100;
  const total = (item.salePrice || 0) + serviceFee;

  return (
    <div className="card-light p-5 space-y-5">
      <div className="flex items-center gap-2 mb-1">
        <ShoppingBag className="w-5 h-5 text-fashion-rose-light" />
        <h3 className="text-text-primary font-semibold text-lg">
          {t("buyNow")}
        </h3>
      </div>

      {/* Price */}
      <div className="text-center py-4">
        <div className="text-3xl font-bold text-fashion-rose-light">
          {item.salePrice} <span className="text-lg">{t("kwd")}</span>
        </div>
        <div className="text-text-muted text-sm line-through mt-1">
          {t("retailPrice")}: {item.retailPrice} {t("kwd")}
        </div>
      </div>

      {/* Savings */}
      <div className="bg-status-success/10 border border-status-success/20 rounded-xl p-3 flex items-center gap-3">
        <TrendingDown className="w-5 h-5 text-status-success flex-shrink-0" />
        <div>
          <span className="text-status-success font-semibold text-sm">
            {t("savings")} {savings} {t("kwd")} ({savingsPercent}%)
          </span>
        </div>
      </div>

      {/* Price breakdown */}
      <div className="space-y-2 border-t border-dark-border pt-4">
        <div className="flex justify-between text-sm">
          <span className="text-text-muted">{t("salePriceLabel")}</span>
          <span className="text-text-secondary">
            {item.salePrice} {t("kwd")}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-text-muted">{t("serviceFee")}</span>
          <span className="text-text-secondary">
            {serviceFee} {t("kwd")}
          </span>
        </div>
        <div className="flex justify-between font-bold text-lg border-t border-dark-border pt-2">
          <span className="text-text-primary">{t("total")}</span>
          <span className="text-fashion-rose-light">
            {total} {t("kwd")}
          </span>
        </div>
      </div>

      {/* Buy button */}
      <button className="w-full bg-fashion-rose text-white font-bold px-8 py-3 rounded-xl hover:bg-fashion-rose/80 transition-all duration-200 shadow-lg shadow-fashion-rose/20 text-center">
        {t("buyNow")}
      </button>

      {/* Trust badge */}
      <div className="flex items-center gap-2 text-text-muted text-xs justify-center">
        <Shield className="w-3.5 h-3.5" />
        <span>حماية المشترية — ضمان الجودة والتوثيق</span>
      </div>
    </div>
  );
}
