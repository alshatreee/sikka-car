"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import ItemCard from "@/components/fashion/ItemCard";
import ItemFilters from "@/components/fashion/ItemFilters";
import { FilterState } from "@/components/fashion/ItemFilters";
import { getItemsByType, MockFashionItem } from "@/lib/mockData";
import { Repeat, Search, Sparkles } from "lucide-react";
import { useState, useMemo } from "react";
import Link from "next/link";

function applyFilters(items: MockFashionItem[], filters: FilterState): MockFashionItem[] {
  let result = [...items];

  if (filters.search) {
    const q = filters.search.toLowerCase();
    result = result.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.titleAr.includes(q) ||
        item.brand.toLowerCase().includes(q) ||
        item.color.includes(q) ||
        item.area.includes(q)
    );
  }
  if (filters.category) result = result.filter((i) => i.category === filters.category);
  if (filters.size) result = result.filter((i) => i.size === filters.size);
  if (filters.occasion) result = result.filter((i) => i.occasion === filters.occasion);
  if (filters.condition) result = result.filter((i) => i.condition === filters.condition);
  if (filters.color) result = result.filter((i) => i.color === filters.color);
  if (filters.brand) result = result.filter((i) => i.brand === filters.brand);

  switch (filters.sort) {
    case "price_asc":
      result.sort((a, b) => (a.rentalPricePerDay || 0) - (b.rentalPricePerDay || 0));
      break;
    case "price_desc":
      result.sort((a, b) => (b.rentalPricePerDay || 0) - (a.rentalPricePerDay || 0));
      break;
    case "rating":
      result.sort((a, b) => b.rating - a.rating);
      break;
    case "popular":
      result.sort((a, b) => b.reviewCount - a.reviewCount);
      break;
    default:
      break;
  }

  return result;
}

export default function RentPage() {
  const { t, isRTL } = useLanguage();
  const allItems = getItemsByType("RENT");
  const [filters, setFilters] = useState<FilterState>({
    search: "", category: "", size: "", occasion: "", condition: "", color: "", brand: "", sort: "newest",
  });

  const filteredItems = useMemo(() => applyFilters(allItems, filters), [allItems, filters]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-fashion-gold/10 flex items-center justify-center">
            <Repeat className="w-5 h-5 text-fashion-gold" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">{t("rent")}</h1>
            <p className="text-text-muted text-sm">
              {filteredItems.length} {isRTL ? "قطعة متاحة" : "items available"}
            </p>
          </div>
        </div>
        {/* Value proposition chip */}
        <div className="hidden sm:flex items-center gap-2 bg-fashion-gold/5 border border-fashion-gold/20 rounded-full px-4 py-2">
          <Sparkles className="w-4 h-4 text-fashion-gold" />
          <span className="text-fashion-gold text-xs font-medium">
            {isRTL ? "وفري حتى ٨٥٪ من سعر الشراء" : "Save up to 85% vs buying"}
          </span>
        </div>
      </div>

      {/* Filters */}
      <ItemFilters mode="rent" onFilterChange={setFilters} />

      {/* Results */}
      {filteredItems.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-6">
          {filteredItems.map((item) => (
            <ItemCard key={item.id} item={item} mode="rent" />
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <div className="w-20 h-20 rounded-full bg-dark-card mx-auto flex items-center justify-center mb-4">
            <Search className="w-8 h-8 text-text-muted" />
          </div>
          <h3 className="text-text-primary font-semibold text-lg mb-2">
            {isRTL ? "ما لقينا نتائج" : "No results found"}
          </h3>
          <p className="text-text-muted text-sm mb-6 max-w-md mx-auto">
            {isRTL
              ? "جربي تغيير الفلاتر أو البحث بكلمات مختلفة"
              : "Try adjusting your filters or search with different keywords"}
          </p>
          <Link
            href="/list"
            className="inline-flex items-center gap-2 text-fashion-gold hover:text-fashion-gold/80 text-sm font-medium transition-colors"
          >
            {isRTL ? "أو أضيفي قطعتك الأولى" : "Or list your first item"}
            {isRTL ? "←" : "→"}
          </Link>
        </div>
      )}
    </div>
  );
}
