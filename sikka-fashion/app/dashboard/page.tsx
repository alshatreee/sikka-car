"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import {
  Package,
  Repeat,
  ShoppingBag,
  Clock,
  CheckCircle2,
  TrendingUp,
  DollarSign,
  Star,
} from "lucide-react";
import { useState } from "react";
import Link from "next/link";

type Tab = "items" | "rentals" | "purchases";

export default function DashboardPage() {
  const { t, isRTL } = useLanguage();
  const [activeTab, setActiveTab] = useState<Tab>("items");

  const stats = [
    { icon: Package, label: isRTL ? "قطعي" : "My Items", value: "3", color: "text-fashion-gold" },
    { icon: Repeat, label: isRTL ? "إيجارات نشطة" : "Active Rentals", value: "1", color: "text-purple-400" },
    { icon: DollarSign, label: isRTL ? "الأرباح" : "Earnings", value: "212 د.ك", color: "text-status-success" },
    { icon: Star, label: isRTL ? "تقييمي" : "My Rating", value: "4.8", color: "text-fashion-gold" },
  ];

  const tabs = [
    { id: "items" as Tab, label: t("myItems"), icon: Package, count: 3 },
    { id: "rentals" as Tab, label: t("myRentals"), icon: Repeat, count: 2 },
    { id: "purchases" as Tab, label: t("myPurchases"), icon: ShoppingBag, count: 1 },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">{t("dashboard")}</h1>
        <Link href="/list" className="btn-primary text-sm py-2 px-4">{t("addItem")}</Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {stats.map((stat, i) => (
          <div key={i} className="card-light p-4 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl bg-dark-surface flex items-center justify-center`}>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
            <div>
              <p className="text-text-muted text-xs">{stat.label}</p>
              <p className="text-text-primary font-bold text-lg">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Earnings Chart Placeholder */}
      <div className="card-light p-5 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-text-primary font-semibold text-sm flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-status-success" />
            {isRTL ? "الأرباح الشهرية" : "Monthly Earnings"}
          </h2>
          <span className="text-status-success text-xs font-medium">+32% ↑</span>
        </div>
        <div className="flex items-end gap-1.5 h-24">
          {[30, 45, 25, 60, 80, 55, 90, 70, 95, 85, 100, 75].map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-sm transition-all"
              style={{
                height: `${h}%`,
                backgroundColor: i === 11 ? "rgb(212, 168, 83)" : "rgb(41, 37, 36)",
              }}
            />
          ))}
        </div>
        <div className="flex justify-between mt-2 text-text-muted text-[10px]">
          <span>{isRTL ? "يناير" : "Jan"}</span>
          <span>{isRTL ? "ديسمبر" : "Dec"}</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap transition-all ${
              activeTab === tab.id
                ? "bg-fashion-gold/10 text-fashion-gold border border-fashion-gold/30"
                : "bg-dark-surface text-text-muted border border-dark-border hover:text-text-secondary"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              activeTab === tab.id ? "bg-fashion-gold/20" : "bg-dark-border"
            }`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === "items" && (
        <div className="space-y-4">
          {[
            { title: "فستان سهرة تالر مارمو ذهبي", status: "approved", type: "RENT", price: "35 د.ك/يوم", rentals: 4, earnings: "140 د.ك" },
            { title: "بدلة ميشكي سوداء أنيقة", status: "pending", type: "BOTH", price: "20 د.ك/يوم", rentals: 0, earnings: "0 د.ك" },
            { title: "طقم بلايزر زارا بريميوم", status: "approved", type: "SALE", price: "65 د.ك", rentals: 0, earnings: "0 د.ك" },
          ].map((item, i) => (
            <div key={i} className="card-light p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-20 bg-dark-surface rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl opacity-30">👗</span>
                </div>
                <div>
                  <h3 className="text-text-primary font-medium text-sm">{item.title}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={
                      item.type === "RENT" ? "badge-rent" :
                      item.type === "SALE" ? "badge-sale" : "badge-both"
                    }>
                      {item.type === "RENT" ? t("forRent") : item.type === "SALE" ? t("forSale") : t("forBoth")}
                    </span>
                    <span className="text-text-muted text-xs">{item.price}</span>
                  </div>
                  {item.rentals > 0 && (
                    <p className="text-status-success text-xs mt-1">
                      {isRTL ? `${item.rentals} عملية تأجير — ${item.earnings} أرباح` : `${item.rentals} rentals — ${item.earnings} earned`}
                    </p>
                  )}
                </div>
              </div>
              <div>
                {item.status === "approved" ? (
                  <span className="flex items-center gap-1 text-status-success text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {t("approved")}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-status-warning text-xs">
                    <Clock className="w-3.5 h-3.5" />
                    {t("pending")}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === "rentals" && (
        <div className="space-y-4">
          {[
            { title: "فستان ريتروفيت سيكوين", dates: "15-18 مارس 2026", amount: "95 د.ك", status: "completed" },
            { title: "بدلة ألكسندر ماكوين", dates: "22-24 أبريل 2026", amount: "117 د.ك", status: "active" },
          ].map((rental, i) => (
            <div key={i} className="card-light p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-20 bg-dark-surface rounded-lg flex items-center justify-center flex-shrink-0">
                  <Repeat className="w-6 h-6 text-fashion-gold opacity-30" />
                </div>
                <div>
                  <h3 className="text-text-primary font-medium text-sm">{rental.title}</h3>
                  <p className="text-text-muted text-xs mt-1">{rental.dates}</p>
                  <p className="text-fashion-gold font-semibold text-sm mt-1">{rental.amount}</p>
                </div>
              </div>
              <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                rental.status === "completed"
                  ? "bg-status-success/10 text-status-success"
                  : "bg-fashion-gold/10 text-fashion-gold"
              }`}>
                {rental.status === "completed"
                  ? (isRTL ? "مكتمل" : "Completed")
                  : (isRTL ? "نشط" : "Active")}
              </span>
            </div>
          ))}
        </div>
      )}

      {activeTab === "purchases" && (
        <div className="space-y-4">
          {[
            { title: "فستان سيلف بورتريت دانتيل ميدي", amount: "168 د.ك", status: "delivered" },
          ].map((purchase, i) => (
            <div key={i} className="card-light p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-20 bg-dark-surface rounded-lg flex items-center justify-center flex-shrink-0">
                  <ShoppingBag className="w-6 h-6 text-fashion-rose-light opacity-30" />
                </div>
                <div>
                  <h3 className="text-text-primary font-medium text-sm">{purchase.title}</h3>
                  <p className="text-fashion-rose-light font-semibold text-sm mt-1">{purchase.amount}</p>
                </div>
              </div>
              <span className="bg-status-success/10 text-status-success text-xs font-medium px-2 py-1 rounded-full">
                {isRTL ? "تم التوصيل" : "Delivered"}
              </span>
            </div>
          ))}

          {/* Empty state for future */}
          {false && (
            <div className="text-center py-12">
              <ShoppingBag className="w-12 h-12 text-text-muted/20 mx-auto mb-3" />
              <p className="text-text-muted">{t("noPurchases")}</p>
              <Link href="/buy" className="btn-primary text-sm mt-4 inline-block">
                {isRTL ? "تصفحي البيع" : "Browse Sales"}
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
