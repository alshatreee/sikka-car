"use client";

import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import ItemCard from "@/components/fashion/ItemCard";
import { getItemsByType, mockItems } from "@/lib/mockData";
import {
  Crown,
  Sparkles,
  BadgeCheck,
  Wallet,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  CheckCircle,
  Truck,
  HelpCircle,
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
        <div className="max-w-7xl mx-auto px-4 py-16 md:py-28 text-center relative">
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

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
            <Link href="/rent" className="btn-solid flex items-center gap-2 justify-center">
              {t("heroRentCTA")}
              <Arrow className="w-4 h-4" />
            </Link>
            <Link href="/buy" className="btn-secondary flex items-center gap-2 justify-center">
              {t("heroBuyCTA")}
              <Arrow className="w-4 h-4" />
            </Link>
          </div>

          {/* How it works link */}
          <Link
            href="/how-it-works"
            className="inline-flex items-center gap-2 text-text-muted hover:text-fashion-gold transition-colors text-sm"
          >
            <HelpCircle className="w-4 h-4" />
            {isRTL ? "كيف تعمل خزانة؟" : "How does Khizana work?"}
          </Link>
        </div>
      </section>

      {/* Trust Badges */}
      <section className="max-w-3xl mx-auto px-4 -mt-4 mb-8">
        <div className="grid grid-cols-3 gap-3">
          {[
            {
              icon: CheckCircle,
              text: isRTL ? "قطع موثّقة" : "Verified Items",
              color: "text-fashion-gold",
            },
            {
              icon: Sparkles,
              text: isRTL ? "تنظيف احترافي" : "Pro Cleaning",
              color: "text-purple-400",
            },
            {
              icon: Truck,
              text: isRTL ? "داخل الكويت" : "Kuwait Delivery",
              color: "text-status-success",
            },
          ].map((badge, i) => (
            <div
              key={i}
              className="flex items-center justify-center gap-2 bg-dark-card/60 border border-dark-border rounded-xl py-3 px-2"
            >
              <badge.icon className={`w-4 h-4 ${badge.color} flex-shrink-0`} />
              <span className="text-text-secondary text-xs font-medium">
                {badge.text}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works - Steps */}
      <section className="max-w-5xl mx-auto px-4 py-12">
        <h2 className="text-xl font-bold text-text-primary text-center mb-8">
          {isRTL ? "كيف تعمل خزانة؟" : "How It Works"}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              step: "1",
              title: isRTL ? "تصفحي" : "Browse",
              desc: isRTL
                ? "اختاري قطعة من مئات الأزياء المصممة"
                : "Choose from hundreds of designer pieces",
            },
            {
              step: "2",
              title: isRTL ? "احجزي أو اشتري" : "Book or Buy",
              desc: isRTL
                ? "حددي تواريخ التأجير أو اشتري مباشرة"
                : "Select rental dates or purchase directly",
            },
            {
              step: "3",
              title: isRTL ? "استلمي" : "Receive",
              desc: isRTL
                ? "توصيل لباب بيتك أو استلام شخصي"
                : "Home delivery or personal pickup",
            },
            {
              step: "4",
              title: isRTL ? "استمتعي وأرجعي" : "Enjoy & Return",
              desc: isRTL
                ? "البسيها واستمتعي، ثم أرجعيها نظيفة"
                : "Wear it, enjoy, then return it clean",
            },
          ].map((s, i) => (
            <div key={i} className="text-center">
              <div className="w-10 h-10 rounded-full bg-fashion-gold/10 border border-fashion-gold/30 flex items-center justify-center mx-auto mb-3">
                <span className="text-fashion-gold font-bold text-sm">
                  {s.step}
                </span>
              </div>
              <h3 className="text-text-primary font-semibold text-sm mb-1">
                {s.title}
              </h3>
              <p className="text-text-muted text-xs leading-relaxed">
                {s.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-4xl mx-auto px-4 py-8">
        <div className="grid grid-cols-3 gap-4">
          {[
            { value: `${mockItems.length}+`, label: isRTL ? "قطعة متاحة" : "Items Available" },
            { value: "15+", label: isRTL ? "ماركة عالمية" : "Global Brands" },
            { value: "4.8", label: isRTL ? "متوسط التقييم" : "Avg. Rating" },
          ].map((stat, i) => (
            <div key={i} className="text-center">
              <div className="text-2xl md:text-3xl font-bold gradient-text">
                {stat.value}
              </div>
              <p className="text-text-muted text-xs mt-1">{stat.label}</p>
            </div>
          ))}
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

      {/* Rental Value Proposition */}
      <section className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-gradient-to-l from-fashion-gold/5 to-fashion-gold/10 border border-fashion-gold/20 rounded-2xl p-6 md:p-8 text-center">
          <h3 className="text-xl font-bold text-text-primary mb-2">
            {isRTL
              ? "ليش تشترين فستان بـ 680 د.ك وتلبسينه مرة وحدة؟"
              : "Why buy a 680 KWD dress you'll wear once?"}
          </h3>
          <p className="text-text-muted text-sm mb-4">
            {isRTL
              ? "استأجريه بـ 80 د.ك فقط — وفّري 88% واستمتعي بنفس الإطلالة"
              : "Rent it for just 80 KWD — save 88% and enjoy the same look"}
          </p>
          <Link href="/rent" className="btn-primary text-sm inline-flex items-center gap-2">
            {t("heroRentCTA")}
            <Arrow className="w-4 h-4" />
          </Link>
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

      {/* CTA - List Your Item */}
      <section className="max-w-4xl mx-auto px-4 py-12">
        <div className="bg-dark-card border border-dark-border rounded-2xl p-8 text-center">
          <h3 className="text-xl font-bold text-text-primary mb-2">
            {isRTL
              ? "عندك أزياء مصممة ما تلبسينها؟"
              : "Have designer pieces you don't wear?"}
          </h3>
          <p className="text-text-muted text-sm mb-6">
            {isRTL
              ? "حوّلي خزانتك لمصدر دخل — أجّري أو بيعي قطعك بأمان"
              : "Turn your closet into income — rent or sell safely"}
          </p>
          <Link href="/list" className="btn-solid inline-flex items-center gap-2">
            {t("list")}
            <Arrow className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
