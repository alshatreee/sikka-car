"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import BuyPanel from "@/components/fashion/BuyPanel";
import { getItemById } from "@/lib/mockData";
import {
  ArrowRight,
  ArrowLeft,
  Star,
  MapPin,
  Tag,
  Ruler,
  Palette,
  Sparkles,
  User,
} from "lucide-react";

export default function BuyDetailPage() {
  const { id } = useParams();
  const { t, isRTL } = useLanguage();
  const item = getItemById(id as string);
  const BackArrow = isRTL ? ArrowRight : ArrowLeft;

  if (!item) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <p className="text-text-muted text-lg">القطعة غير موجودة</p>
        <Link href="/buy" className="btn-primary mt-4 inline-block">
          {t("buy")}
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Back */}
      <Link
        href="/buy"
        className="inline-flex items-center gap-2 text-text-muted hover:text-fashion-rose-light mb-6 transition-colors"
      >
        <BackArrow className="w-4 h-4" />
        <span className="text-sm">{t("buy")}</span>
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Image Gallery */}
        <div className="lg:col-span-2">
          <div className="aspect-[4/5] md:aspect-[3/4] bg-dark-surface rounded-2xl overflow-hidden flex items-center justify-center">
            <div className="text-center">
              <span className="text-8xl opacity-20">👗</span>
              <p className="text-text-muted text-sm mt-2">صورة القطعة</p>
            </div>
          </div>

          {/* Details */}
          <div className="mt-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="badge-sale mb-2 inline-block">{t("forSale")}</span>
                <h1 className="text-2xl md:text-3xl font-bold text-text-primary mt-1">
                  {isRTL ? item.titleAr : item.title}
                </h1>
              </div>
              <div className="flex items-center gap-1 bg-dark-surface rounded-lg px-3 py-1.5">
                <Star className="w-4 h-4 fill-fashion-gold text-fashion-gold" />
                <span className="text-text-primary font-semibold text-sm">
                  {item.rating}
                </span>
                <span className="text-text-muted text-xs">
                  ({item.reviewCount})
                </span>
              </div>
            </div>

            {/* Info Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { icon: Tag, label: t("brand"), value: item.brand },
                { icon: Ruler, label: t("size"), value: t(item.size as any) },
                { icon: Palette, label: "اللون", value: item.color },
                {
                  icon: Sparkles,
                  label: t("condition"),
                  value: t(item.condition as any),
                },
              ].map((info, i) => (
                <div key={i} className="card-light p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <info.icon className="w-3.5 h-3.5 text-text-muted" />
                    <span className="text-text-muted text-xs">{info.label}</span>
                  </div>
                  <p className="text-text-primary font-medium text-sm">
                    {info.value}
                  </p>
                </div>
              ))}
            </div>

            {/* Owner */}
            <div className="card-light p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-fashion-rose/20 flex items-center justify-center">
                <User className="w-5 h-5 text-fashion-rose-light" />
              </div>
              <div>
                <p className="text-text-primary font-medium text-sm">
                  {item.ownerName}
                </p>
                <div className="flex items-center gap-1 text-text-muted text-xs">
                  <MapPin className="w-3 h-3" />
                  {item.area}
                </div>
              </div>
            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-2">
              <span className="bg-dark-surface text-text-secondary text-xs px-3 py-1.5 rounded-lg">
                {t(item.category as any)}
              </span>
              <span className="bg-dark-surface text-text-secondary text-xs px-3 py-1.5 rounded-lg">
                {t(item.occasion as any)}
              </span>
            </div>
          </div>
        </div>

        {/* Buy Panel */}
        <div className="lg:col-span-1">
          <div className="sticky top-20">
            <BuyPanel item={item} />
          </div>
        </div>
      </div>
    </div>
  );
}
