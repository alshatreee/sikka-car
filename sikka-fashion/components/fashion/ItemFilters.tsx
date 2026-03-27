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
  sort: string;
}

const categories = ["SUIT", "BLAZER", "DRESS", "EVENING_GOWN", "ABAYA", "JUMPSUIT", "SKIRT_SET", "OTHER"];
const sizes = ["XS", "S", "M", "L", "XL", "XXL"];
const occasions = ["WEDDING", "FORMAL", "BUSINESS", "PARTY", "GRADUATION", "ENGAGEMENT", "EID", "NATIONAL_DAY"];
const conditions = ["NEW_WITH_TAGS", "EXCELLENT", "VERY_GOOD", "GOOD"];

export default function ItemFilters({ mode, onFilterChange }: ItemFiltersProps) {
  const { t } = useLanguage();
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    search: "",
    category: "",
    size: "",
    occasion: "",
    condition: "",
    sort: "newest",
  });

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
            placeholder={t("search")}
            value={filters.search}
            onChange={(e) => updateFilter("search", e.target.value)}
            className="input-field ps-10"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border transition-all ${
            showFilters
              ? "border-fashion-gold bg-fashion-gold/10 text-fashion-gold"
              : "border-dark-border text-text-muted hover:border-fashion-gold/50"
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span className="text-sm hidden sm:inline">{t("filter")}</span>
        </button>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <div className="card-light p-4 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* Category */}
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

            {/* Size */}
            <select
              value={filters.size}
              onChange={(e) => updateFilter("size", e.target.value)}
              className="input-field text-sm"
            >
              <option value="">{t("allSizes")}</option>
              {sizes.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>

            {/* Occasion */}
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

            {/* Condition */}
            {mode === "buy" && (
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
            )}

            {/* Sort */}
            <select
              value={filters.sort}
              onChange={(e) => updateFilter("sort", e.target.value)}
              className="input-field text-sm"
            >
              <option value="newest">{t("newest")}</option>
              <option value="price_asc">{t("priceLowHigh")}</option>
              <option value="price_desc">{t("priceHighLow")}</option>
            </select>
          </div>

          <button
            onClick={resetFilters}
            className="flex items-center gap-1 text-text-muted hover:text-fashion-gold text-sm transition-colors"
          >
            <X className="w-3 h-3" />
            {t("reset")}
          </button>
        </div>
      )}
    </div>
  );
}
