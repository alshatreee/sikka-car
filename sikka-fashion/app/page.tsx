"use client";

import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import ItemCard from "@/components/fashion/ItemCard";
import { getItemsByType } from "@/lib/mockData";
import {
  Crown,
  Sparkles,
  BadgeCheck,
  Wallet,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";

export default function HomePage() {
  const { t, isRTL } = useLanguage();
  const rentalItems = getItemsByType("RENT").slice(0, 4);
  const saleItems = getItemsByType("SALE").slice(0, 4);
  const Arrow = isRTL ? ArrowLeft : ArrowRight;

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-fashion-gold/5 via-transparent to-transparent" />
        <div className="max-w-7xl mx-auto px-4 py-20 md:py-32 text-center relative">
          <div className="inline-flex items-center gap-2 bg-fashion-gold/10 border border-fashion-gold/20 rounded-full px-4 py-1.5 mb-6">
            <Crown className="w-4 h-4 text-fashion-gold" />
            <span className="text-fashion-gold text-sm font-medium">
              {isRTL ? "الكويت" : "Kuwait"}
            </span>
          </div>

          <h1 className="text-4xl md:text-6xl font-bold text-text-primary mb-4 leading-tight">
            {t("heroTitle")}
          </h1>
          <p className="text-text-muted text-lg md:text-xl mb-8 max-w-2xl mx-auto">
            {t("heroSubtitle")}
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/rent" className="btn-solid flex items-center gap-2 justify-center">
              {t("heroRentCTA")}
              <Arrow className="w-4 h-4" />
            </Link>
            <Link href="/buy" className="btn-secondary flex items-center gap-2 justify-center">
              {t("heroBuyCTA")}
              <Arrow className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Latest Rentals */}
      <section className="max-w-7xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-text-primary">
            {t("latestRentals")}
          </h2>
          <Link
            href="/rent"
            className="text-fashion-gold text-sm font-medium flex items-center gap-1 hover:underline"
          >
            {t("viewAll")}
            <Arrow className="w-3.5 h-3.5" />
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {rentalItems.map((item) => (
            <ItemCard key={item.id} item={item} mode="rent" />
          ))}
        </div>
      </section>

      {/* Latest Sales */}
      <section className="max-w-7xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-text-primary">
            {t("latestSales")}
          </h2>
          <Link
            href="/buy"
            className="text-fashion-rose-light text-sm font-medium flex items-center gap-1 hover:underline"
          >
            {t("viewAll")}
            <Arrow className="w-3.5 h-3.5" />
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {saleItems.map((item) => (
            <ItemCard key={item.id} item={item} mode="buy" />
          ))}
        </div>
      </section>

      {/* Why Us */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <h2 className="text-2xl font-bold text-text-primary text-center mb-10">
          {t("whyUs")}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            {
              icon: BadgeCheck,
              title: t("feature1Title"),
              desc: t("feature1Desc"),
              color: "text-fashion-gold",
            },
            {
              icon: Wallet,
              title: t("feature2Title"),
              desc: t("feature2Desc"),
              color: "text-status-success",
            },
            {
              icon: Sparkles,
              title: t("feature3Title"),
              desc: t("feature3Desc"),
              color: "text-purple-400",
            },
            {
              icon: ShieldCheck,
              title: t("feature4Title"),
              desc: t("feature4Desc"),
              color: "text-fashion-rose-light",
            },
          ].map((feature, i) => (
            <div key={i} className="card-light p-5 text-center">
              <feature.icon
                className={`w-8 h-8 ${feature.color} mx-auto mb-3`}
              />
              <h3 className="text-text-primary font-semibold text-sm mb-2">
                {feature.title}
              </h3>
              <p className="text-text-muted text-xs leading-relaxed">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
