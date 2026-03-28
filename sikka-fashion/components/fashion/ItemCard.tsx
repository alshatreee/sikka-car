"use client";

import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import { Star, MapPin, Tag } from "lucide-react";
import { MockFashionItem } from "@/lib/mockData";

interface ItemCardProps {
  item: MockFashionItem;
  mode?: "rent" | "buy";
}

export default function ItemCard({ item, mode }: ItemCardProps) {
  const { t, isRTL } = useLanguage();

  const href =
    mode === "buy" || (item.listingType === "SALE" && mode !== "rent")
      ? `/buy/${item.id}`
      : `/rent/${item.id}`;

  const badgeClass =
    item.listingType === "RENT"
      ? "badge-rent"
      : item.listingType === "SALE"
      ? "badge-sale"
      : "badge-both";

  const badgeText =
    item.listingType === "RENT"
      ? t("forRent")
      : item.listingType === "SALE"
      ? t("forSale")
      : t("forBoth");

  // Calculate savings percentage for sale items
  const savingsPercent =
    item.salePrice && item.retailPrice
      ? Math.round((1 - item.salePrice / item.retailPrice) * 100)
      : null;

  // Calculate rent vs buy savings
  const rentSavingsPercent =
    item.rentalPricePerDay && item.retailPrice
      ? Math.round((1 - item.rentalPricePerDay / item.retailPrice) * 100)
      : null;

  return (
    <Link href={href} className="card group cursor-pointer overflow-hidden">
      {/* Image */}
      <div className="relative aspect-[3/4] bg-dark-surface overflow-hidden">
        <div className="w-full h-full bg-gradient-to-br from-dark-surface to-dark-border flex items-center justify-center group-hover:scale-105 transition-transform duration-500">
          <span className="text-4xl opacity-30">👗</span>
        </div>
        {/* Badge */}
        <div className="absolute top-3 start-3">
          <span className={badgeClass}>{badgeText}</span>
        </div>
        {/* Savings badge */}
        {mode === "buy" && savingsPercent && savingsPercent > 0 && (
          <div className="absolute top-3 end-3">
            <span className="bg-green-500/90 text-white text-[10px] font-bold px-2 py-1 rounded-lg flex items-center gap-0.5">
              <Tag className="w-3 h-3" />
              {savingsPercent}%-
            </span>
          </div>
        )}
        {mode === "rent" && rentSavingsPercent && rentSavingsPercent > 0 && (
          <div className="absolute top-3 end-3">
            <span className="bg-fashion-gold/90 text-dark-bg text-[10px] font-bold px-2 py-1 rounded-lg">
              {isRTL ? `وفري ${rentSavingsPercent}٪` : `Save ${rentSavingsPercent}%`}
            </span>
          </div>
        )}
        {/* Brand */}
        <div className="absolute bottom-3 start-3">
          <span className="bg-dark-bg/80 backdrop-blur-sm text-text-secondary text-xs px-2 py-1 rounded-lg">
            {item.brand}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="text-text-primary font-medium text-sm truncate mb-1">
          {isRTL ? item.titleAr : item.title}
        </h3>

        <div className="flex items-center gap-1 text-text-muted text-xs mb-2">
          <MapPin className="w-3 h-3 flex-shrink-0" />
          <span>{item.area}</span>
          <span className="mx-1">•</span>
          <span>{t(item.size as any)}</span>
          <span className="mx-1">•</span>
          <span>{t(item.condition as any)}</span>
        </div>

        {/* Rating */}
        <div className="flex items-center gap-1 mb-2">
          <Star className="w-3.5 h-3.5 fill-fashion-gold text-fashion-gold" />
          <span className="text-text-secondary text-xs font-medium">
            {item.rating}
          </span>
          <span className="text-text-muted text-xs">
            ({item.reviewCount})
          </span>
        </div>

        {/* Price */}
        <div className="flex items-center justify-between">
          {item.rentalPricePerDay && (mode === "rent" || !mode) && (
            <div className="flex items-baseline gap-1">
              <span className="text-fashion-gold font-bold text-lg">
                {item.rentalPricePerDay}
              </span>
              <span className="text-text-muted text-xs">
                {t("kwd")} {t("perDay")}
              </span>
            </div>
          )}
          {item.salePrice && (mode === "buy" || (!mode && !item.rentalPricePerDay)) && (
            <div>
              <div className="flex items-baseline gap-1">
                <span className="text-fashion-rose-light font-bold text-lg">
                  {item.salePrice}
                </span>
                <span className="text-text-muted text-xs">{t("kwd")}</span>
              </div>
              {item.retailPrice && (
                <span className="text-text-muted text-[10px] line-through">
                  {item.retailPrice} {t("kwd")}
                </span>
              )}
            </div>
          )}
          {item.salePrice && item.rentalPricePerDay && !mode && (
            <div className="flex items-baseline gap-1">
              <span className="text-fashion-gold font-bold text-lg">
                {item.rentalPricePerDay}
              </span>
              <span className="text-text-muted text-xs">
                {t("kwd")} {t("perDay")}
              </span>
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
