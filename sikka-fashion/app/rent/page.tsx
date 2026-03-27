"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import ItemCard from "@/components/fashion/ItemCard";
import ItemFilters from "@/components/fashion/ItemFilters";
import { getItemsByType } from "@/lib/mockData";
import { Repeat } from "lucide-react";

export default function RentPage() {
  const { t } = useLanguage();
  const items = getItemsByType("RENT");

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-fashion-gold/10 flex items-center justify-center">
          <Repeat className="w-5 h-5 text-fashion-gold" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {t("rent")}
          </h1>
          <p className="text-text-muted text-sm">
            {items.length} {t("forRent")}
          </p>
        </div>
      </div>

      {/* Filters */}
      <ItemFilters mode="rent" />

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-6">
        {items.map((item) => (
          <ItemCard key={item.id} item={item} mode="rent" />
        ))}
      </div>

      {items.length === 0 && (
        <div className="text-center py-20">
          <p className="text-text-muted text-lg">لا توجد قطع متاحة للتأجير حالياً</p>
        </div>
      )}
    </div>
  );
}
