"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import RentalPanel from "@/components/fashion/RentalPanel";
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
  ShieldCheck,
  Clock,
  Repeat,
  CheckCircle,
  XCircle,
  Info,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";

export default function RentDetailPage() {
  const { id } = useParams();
  const { t, isRTL } = useLanguage();
  const item = getItemById(id as string);
  const BackArrow = isRTL ? ArrowRight : ArrowLeft;
  const [activeImage, setActiveImage] = useState(0);

  if (!item) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <p className="text-text-muted text-lg">
          {isRTL ? "القطعة غير موجودة" : "Item not found"}
        </p>
        <Link href="/rent" className="btn-primary mt-4 inline-block">
          {t("rent")}
        </Link>
      </div>
    );
  }

  const galleryImages = [
    { label: isRTL ? "أمامي" : "Front" },
    { label: isRTL ? "جانبي" : "Side" },
    { label: isRTL ? "خلفي" : "Back" },
    { label: isRTL ? "تفاصيل" : "Detail" },
  ];

  const savingsVsBuy = item.retailPrice - (item.rentalPricePerDay || 0) * 3;
  const savingsPercent = Math.round(
    (savingsVsBuy / item.retailPrice) * 100
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 pb-28 md:pb-8">
      {/* Back */}
      <Link
        href="/rent"
        className="inline-flex items-center gap-2 text-text-muted hover:text-fashion-gold mb-6 transition-colors"
      >
        <BackArrow className="w-4 h-4" />
        <span className="text-sm">{t("rent")}</span>
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Image Gallery */}
        <div className="lg:col-span-2">
          {/* Main Image */}
          <div className="aspect-[4/5] md:aspect-[3/4] bg-dark-surface rounded-2xl overflow-hidden flex items-center justify-center relative group">
            <div className="text-center">
              <span className="text-8xl opacity-20">👗</span>
              <p className="text-text-muted text-sm mt-2">
                {galleryImages[activeImage]?.label}
              </p>
            </div>
            {/* Nav arrows */}
            <button
              onClick={() =>
                setActiveImage((p) =>
                  p > 0 ? p - 1 : galleryImages.length - 1
                )
              }
              className="absolute start-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-dark-bg/70 flex items-center justify-center text-text-secondary hover:text-fashion-gold opacity-0 group-hover:opacity-100 transition-opacity"
            >
              {isRTL ? (
                <ChevronRight className="w-5 h-5" />
              ) : (
                <ChevronLeft className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={() =>
                setActiveImage((p) =>
                  p < galleryImages.length - 1 ? p + 1 : 0
                )
              }
              className="absolute end-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-dark-bg/70 flex items-center justify-center text-text-secondary hover:text-fashion-gold opacity-0 group-hover:opacity-100 transition-opacity"
            >
              {isRTL ? (
                <ChevronLeft className="w-5 h-5" />
              ) : (
                <ChevronRight className="w-5 h-5" />
              )}
            </button>
            {/* Image counter */}
            <div className="absolute bottom-3 start-1/2 -translate-x-1/2 bg-dark-bg/70 text-text-muted text-xs px-3 py-1 rounded-full">
              {activeImage + 1} / {galleryImages.length}
            </div>
          </div>

          {/* Thumbnails */}
          <div className="flex gap-2 mt-3">
            {galleryImages.map((img, i) => (
              <button
                key={i}
                onClick={() => setActiveImage(i)}
                className={`flex-1 aspect-square rounded-lg bg-dark-surface flex items-center justify-center text-xs transition-all ${
                  activeImage === i
                    ? "border-2 border-fashion-gold"
                    : "border border-dark-border opacity-60 hover:opacity-100"
                }`}
              >
                <span className="text-2xl opacity-20">👗</span>
              </button>
            ))}
          </div>

          {/* Details */}
          <div className="mt-6 space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <span className="badge-rent mb-2 inline-block">
                  {t("forRent")}
                </span>
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

            {/* Rental Value Highlight */}
            <div className="bg-status-success/10 border border-status-success/20 rounded-xl p-3 flex items-center gap-3">
              <Repeat className="w-5 h-5 text-status-success flex-shrink-0" />
              <p className="text-status-success text-sm font-medium">
                {isRTL
                  ? `بدل شراء القطعة بـ ${item.retailPrice} د.ك، استأجريها بـ ${item.rentalPricePerDay} د.ك/يوم — وفّري ${savingsPercent}%`
                  : `Instead of buying at ${item.retailPrice} KWD, rent for ${item.rentalPricePerDay} KWD/day — save ${savingsPercent}%`}
              </p>
            </div>

            {/* Info Grid - Extended */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { icon: Tag, label: t("brand"), value: item.brand },
                {
                  icon: Ruler,
                  label: t("size"),
                  value: t(item.size as any),
                },
                { icon: Palette, label: isRTL ? "اللون" : "Color", value: item.color },
                {
                  icon: Sparkles,
                  label: t("condition"),
                  value: t(item.condition as any),
                },
              ].map((info, i) => (
                <div key={i} className="card-light p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <info.icon className="w-3.5 h-3.5 text-text-muted" />
                    <span className="text-text-muted text-xs">
                      {info.label}
                    </span>
                  </div>
                  <p className="text-text-primary font-medium text-sm">
                    {info.value}
                  </p>
                </div>
              ))}
            </div>

            {/* Measurements */}
            <div className="card-light p-4">
              <h3 className="text-text-primary font-semibold text-sm mb-3 flex items-center gap-2">
                <Ruler className="w-4 h-4 text-fashion-gold" />
                {isRTL ? "القياسات التقريبية" : "Approximate Measurements"}
              </h3>
              <div className="grid grid-cols-3 gap-3 text-center">
                {[
                  { label: isRTL ? "الصدر" : "Bust", value: "88 cm" },
                  { label: isRTL ? "الخصر" : "Waist", value: "70 cm" },
                  { label: isRTL ? "الطول" : "Length", value: "145 cm" },
                ].map((m, i) => (
                  <div key={i}>
                    <p className="text-text-muted text-xs">{m.label}</p>
                    <p className="text-text-primary font-medium text-sm">
                      {m.value}
                    </p>
                  </div>
                ))}
              </div>
              <p className="text-text-muted text-xs mt-3 flex items-start gap-1">
                <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                {isRTL
                  ? "القياسات تقريبية — تواصلي مع المالكة للتأكد من المقاس"
                  : "Measurements are approximate — contact the owner to confirm fit"}
              </p>
            </div>

            {/* Owner */}
            <div className="card-light p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-fashion-gold/20 flex items-center justify-center">
                  <User className="w-5 h-5 text-fashion-gold" />
                </div>
                <div>
                  <p className="text-text-primary font-medium text-sm">
                    {item.ownerName}
                  </p>
                  <div className="flex items-center gap-2 text-text-muted text-xs">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {item.area}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {isRTL ? "تستجيب خلال ساعة" : "Responds within 1h"}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1 text-status-success text-xs">
                <CheckCircle className="w-3.5 h-3.5" />
                {isRTL ? "موثّقة" : "Verified"}
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
              <span className="bg-dark-surface text-text-secondary text-xs px-3 py-1.5 rounded-lg flex items-center gap-1">
                <Repeat className="w-3 h-3" />
                {isRTL ? `تم تأجيرها ${item.reviewCount} مرة` : `Rented ${item.reviewCount} times`}
              </span>
            </div>

            {/* Policies */}
            <div className="card-light p-4 space-y-3">
              <h3 className="text-text-primary font-semibold text-sm">
                {isRTL ? "السياسات" : "Policies"}
              </h3>
              <div className="space-y-2">
                {[
                  {
                    icon: CheckCircle,
                    text: isRTL
                      ? "إلغاء مجاني حتى 48 ساعة قبل الموعد"
                      : "Free cancellation up to 48h before",
                    ok: true,
                  },
                  {
                    icon: CheckCircle,
                    text: isRTL
                      ? "التسليم: مندوب أو استلام شخصي من المنطقة"
                      : "Delivery: courier or personal pickup",
                    ok: true,
                  },
                  {
                    icon: CheckCircle,
                    text: isRTL
                      ? "التأخير: 10 د.ك رسوم يوم إضافي"
                      : "Late return: 10 KWD per extra day",
                    ok: true,
                  },
                  {
                    icon: XCircle,
                    text: isRTL
                      ? "التلف: يتحمل المستأجر تكلفة الإصلاح أو القيمة"
                      : "Damage: renter covers repair or item value",
                    ok: false,
                  },
                ].map((policy, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-xs"
                  >
                    <policy.icon
                      className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
                        policy.ok ? "text-status-success" : "text-status-warning"
                      }`}
                    />
                    <span className="text-text-muted">{policy.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Rental Panel - Desktop */}
        <div className="lg:col-span-1 hidden lg:block">
          <div className="sticky top-20">
            <div className="text-center mb-4">
              <span className="text-3xl font-bold text-fashion-gold">
                {item.rentalPricePerDay}
              </span>
              <span className="text-text-muted text-sm ms-1">
                {t("kwd")} {t("perDay")}
              </span>
            </div>

            {/* Trust badges before CTA */}
            <div className="flex items-center justify-center gap-4 mb-4 text-xs text-text-muted">
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-fashion-gold" />
                {isRTL ? "توثيق الماركة" : "Brand Verified"}
              </span>
              <span className="flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                {isRTL ? "تنظيف مشمول" : "Cleaning Included"}
              </span>
            </div>

            <RentalPanel item={item} />
          </div>
        </div>
      </div>

      {/* Mobile Fixed CTA */}
      <div className="lg:hidden fixed bottom-16 left-0 right-0 z-40 bg-dark-bg/95 backdrop-blur-md border-t border-dark-border px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xl font-bold text-fashion-gold">
              {item.rentalPricePerDay}
            </span>
            <span className="text-text-muted text-xs ms-1">
              {t("kwd")} {t("perDay")}
            </span>
          </div>
          <button className="btn-solid py-2.5 px-6 text-sm">
            {t("bookNow")}
          </button>
        </div>
      </div>
    </div>
  );
}
