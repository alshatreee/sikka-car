"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import ItemCard from "@/components/fashion/ItemCard";
import ItemFilters from "@/components/fashion/ItemFilters";
import { getItemsByType } from "@/lib/mockData";
import { ShoppingBag } from "lucide-react";

export default function BuyPage() {
  const { t } = useLanguage();
  const items = getItemsByType("SALE");

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-fashion-rose/10 flex items-center justify-center">
          <ShoppingBag className="w-5 h-5 text-fashion-rose-light" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {t("buy")}
          </h1>
          <p className="text-text-muted text-sm">
            {items.length} {t("forSale")}
          </p>
        </div>
      </div>

      {/* Filters */}
      <ItemFilters mode="buy" />

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-6">
        {items.map((item) => (
          <ItemCard key={item.id} item={item} mode="buy" />
        ))}
      </div>

      {items.length === 0 && (
        <div className="text-center py-20">
          <p className="text-text-muted text-lg">لا توجد قطع متاحة للبيع حالياً</p>
        </div>
      )}
    </div>
  );
}
