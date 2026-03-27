"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import { Package, Repeat, ShoppingBag, Clock, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import Link from "next/link";

type Tab = "items" | "rentals" | "purchases";

export default function DashboardPage() {
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState<Tab>("items");

  const tabs = [
    { id: "items" as Tab, label: t("myItems"), icon: Package, count: 3 },
    { id: "rentals" as Tab, label: t("myRentals"), icon: Repeat, count: 2 },
    { id: "purchases" as Tab, label: t("myPurchases"), icon: ShoppingBag, count: 1 },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-text-primary">
          {t("dashboard")}
        </h1>
        <Link href="/list" className="btn-primary text-sm py-2 px-4">
          {t("addItem")}
        </Link>
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
          {/* Sample items */}
          {[
            { title: "فستان سهرة تالر مارمو ذهبي", status: "approved", type: "RENT", price: "35 د.ك/يوم", rentals: 4 },
            { title: "بدلة ميشكي سوداء أنيقة", status: "pending", type: "BOTH", price: "20 د.ك/يوم", rentals: 0 },
            { title: "طقم بلايزر زارا بريميوم", status: "approved", type: "SALE", price: "65 د.ك", rentals: 0 },
          ].map((item, i) => (
            <div key={i} className="card-light p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-20 bg-dark-surface rounded-lg flex items-center justify-center">
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
                </div>
              </div>
              <div className="flex items-center gap-2">
                {item.status === "approved" ? (
                  <span className="flex items-center gap-1 text-status-success text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {t("approved")}
                  </span>
                ) : item.status === "pending" ? (
                  <span className="flex items-center gap-1 text-status-warning text-xs">
                    <Clock className="w-3.5 h-3.5" />
                    {t("pending")}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-status-error text-xs">
                    <XCircle className="w-3.5 h-3.5" />
                    {t("rejected")}
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
                <div className="w-16 h-20 bg-dark-surface rounded-lg flex items-center justify-center">
                  <Repeat className="w-6 h-6 text-fashion-gold opacity-30" />
                </div>
                <div>
                  <h3 className="text-text-primary font-medium text-sm">{rental.title}</h3>
                  <p className="text-text-muted text-xs mt-1">{rental.dates}</p>
                  <p className="text-fashion-gold font-semibold text-sm mt-1">{rental.amount}</p>
                </div>
              </div>
              <span className={`text-xs font-medium ${
                rental.status === "completed" ? "text-status-success" :
                rental.status === "active" ? "text-fashion-gold" : "text-status-warning"
              }`}>
                {t(rental.status as any)}
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
                <div className="w-16 h-20 bg-dark-surface rounded-lg flex items-center justify-center">
                  <ShoppingBag className="w-6 h-6 text-fashion-rose-light opacity-30" />
                </div>
                <div>
                  <h3 className="text-text-primary font-medium text-sm">{purchase.title}</h3>
                  <p className="text-fashion-rose-light font-semibold text-sm mt-1">{purchase.amount}</p>
                </div>
              </div>
              <span className="text-status-success text-xs font-medium">
                تم التوصيل
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
