"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";

interface ItemFiltersProps {
  mode: "rent" | "buy";
  onFilterChange?: (filters: FilterState) => void;
}

export interface FilterState {
  search: string;
  category: string;
  size: string;
  occasion: string;
  condition: string;
  color: string;
  brand: string;
  sort: string;
}

const categories = ["SUIT", "BLAZER", "DRESS", "EVENING_GOWN", "ABAYA", "JUMPSUIT", "SKIRT_SET", "OTHER"];
const sizes = ["XS", "S", "M", "L", "XL", "XXL"];
const occasions = ["WEDDING", "FORMAL", "BUSINESS", "PARTY", "GRADUATION", "ENGAGEMENT", "EID", "NATIONAL_DAY"];
const conditions = ["NEW_WITH_TAGS", "EXCELLENT", "VERY_GOOD", "GOOD"];
const colors = [
  { value: "أسود", label_ar: "أسود", label_en: "Black" },
  { value: "أبيض", label_ar: "أبيض", label_en: "White" },
  { value: "ذهبي", label_ar: "ذهبي", label_en: "Gold" },
  { value: "فضي", label_ar: "فضي", label_en: "Silver" },
  { value: "وردي", label_ar: "وردي", label_en: "Pink" },
  { value: "أحمر", label_ar: "أحمر", label_en: "Red" },
  { value: "كحلي", label_ar: "كحلي", label_en: "Navy" },
  { value: "بيج", label_ar: "بيج", label_en: "Beige" },
];
const brands = ["Elie Saab", "Taller Marmo", "Meshki", "Retrofete", "Zara", "Self-Portrait", "Alexander McQueen", "Bambah"];

export default function ItemFilters({ onFilterChange }: ItemFiltersProps) {
  const { t, isRTL } = useLanguage();
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    search: "",
    category: "",
    size: "",
    occasion: "",
    condition: "",
    color: "",
    brand: "",
    sort: "newest",
  });

  const activeCount = Object.entries(filters).filter(
    ([key, val]) => val && key !== "sort" && key !== "search"
  ).length;

  const updateFilter = (key: keyof FilterState, value: string) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    onFilterChange?.(newFilters);
  };

  const resetFilters = () => {
    const newFilters: FilterState = {
      search: "",
      category: "",
      size: "",
      occasion: "",
      condition: "",
      color: "",
      brand: "",
      sort: "newest",
    };
    setFilters(newFilters);
    onFilterChange?.(newFilters);
  };

  return (
    <div className="space-y-4">
      {/* Search + Toggle */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder={isRTL ? "ابحثي بالاسم، الماركة، اللون، أو المناسبة..." : "Search by name, brand, color, or occasion..."}
            value={filters.search}
            onChange={(e) => updateFilter("search", e.target.value)}
            className="input-field ps-10"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border transition-all relative ${
            showFilters
              ? "border-fashion-gold bg-fashion-gold/10 text-fashion-gold"
              : "border-dark-border text-text-muted hover:border-fashion-gold/50"
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span className="text-sm hidden sm:inline">{t("filter")}</span>
          {activeCount > 0 && (
            <span className="absolute -top-1.5 -end-1.5 w-5 h-5 rounded-full bg-fashion-gold text-dark-bg text-xs font-bold flex items-center justify-center">
              {activeCount}
            </span>
          )}
        </button>
      </div>

      {/* Sort Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <span className="text-text-muted text-xs flex-shrink-0">{t("sort")}:</span>
        {[
          { value: "newest", label: t("newest") },
          { value: "price_asc", label: t("priceLowHigh") },
          { value: "price_desc", label: t("priceHighLow") },
          { value: "rating", label: isRTL ? "الأعلى تقييماً" : "Top Rated" },
          { value: "popular", label: isRTL ? "الأكثر طلباً" : "Most Popular" },
        ].map((option) => (
          <button
            key={option.value}
            onClick={() => updateFilter("sort", option.value)}
            className={`text-xs px-3 py-1.5 rounded-full whitespace-nowrap transition-all ${
              filters.sort === option.value
                ? "bg-fashion-gold/10 text-fashion-gold border border-fashion-gold/30"
                : "text-text-muted hover:text-text-secondary border border-dark-border"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <div className="card-light p-4 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {/* Category */}
            <div>
              <label className="text-text-muted text-xs mb-1 block">{t("allCategories")}</label>
              <select
                value={filters.category}
                onChange={(e) => updateFilter("category", e.target.value)}
                className="input-field text-sm"
              >
                <option value="">{t("allCategories")}</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {t(cat as any)}
                  </option>
                ))}
              </select>
            </div>

            {/* Size */}
            <div>
              <label className="text-text-muted text-xs mb-1 block">{t("size")}</label>
              <select
                value={filters.size}
                onChange={(e) => updateFilter("size", e.target.value)}
                className="input-field text-sm"
              >
                <option value="">{t("allSizes")}</option>
                {sizes.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </div>

            {/* Occasion */}
            <div>
              <label className="text-text-muted text-xs mb-1 block">{isRTL ? "المناسبة" : "Occasion"}</label>
              <select
                value={filters.occasion}
                onChange={(e) => updateFilter("occasion", e.target.value)}
                className="input-field text-sm"
              >
                <option value="">{t("allOccasions")}</option>
                {occasions.map((occ) => (
                  <option key={occ} value={occ}>
                    {t(occ as any)}
                  </option>
                ))}
              </select>
            </div>

            {/* Brand */}
            <div>
              <label className="text-text-muted text-xs mb-1 block">{t("brand")}</label>
              <select
                value={filters.brand}
                onChange={(e) => updateFilter("brand", e.target.value)}
                className="input-field text-sm"
              >
                <option value="">{isRTL ? "جميع الماركات" : "All Brands"}</option>
                {brands.map((brand) => (
                  <option key={brand} value={brand}>{brand}</option>
                ))}
              </select>
            </div>

            {/* Color */}
            <div>
              <label className="text-text-muted text-xs mb-1 block">{isRTL ? "اللون" : "Color"}</label>
              <select
                value={filters.color}
                onChange={(e) => updateFilter("color", e.target.value)}
                className="input-field text-sm"
              >
                <option value="">{isRTL ? "جميع الألوان" : "All Colors"}</option>
                {colors.map((color) => (
                  <option key={color.value} value={color.value}>
                    {isRTL ? color.label_ar : color.label_en}
                  </option>
                ))}
              </select>
            </div>

            {/* Condition - show for both but more important for buy */}
            <div>
              <label className="text-text-muted text-xs mb-1 block">{t("condition")}</label>
              <select
                value={filters.condition}
                onChange={(e) => updateFilter("condition", e.target.value)}
                className="input-field text-sm"
              >
                <option value="">{t("allConditions")}</option>
                {conditions.map((cond) => (
                  <option key={cond} value={cond}>
                    {t(cond as any)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Active filters + Reset */}
          <div className="flex items-center justify-between">
            <div className="flex flex-wrap gap-2">
              {Object.entries(filters)
                .filter(([key, val]) => val && key !== "sort" && key !== "search")
                .map(([key, val]) => (
                  <span
                    key={key}
                    className="bg-fashion-gold/10 text-fashion-gold text-xs px-2.5 py-1 rounded-full flex items-center gap-1 cursor-pointer hover:bg-fashion-gold/20"
                    onClick={() => updateFilter(key as keyof FilterState, "")}
                  >
                    {t(val as any) || val}
                    <X className="w-3 h-3" />
                  </span>
                ))}
            </div>
            {activeCount > 0 && (
              <button
                onClick={resetFilters}
                className="flex items-center gap-1 text-text-muted hover:text-fashion-gold text-xs transition-colors"
              >
                <X className="w-3 h-3" />
                {t("reset")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
