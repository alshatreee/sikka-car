"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import { Calendar, Sparkles, Shield } from "lucide-react";
import { useState } from "react";
import { MockFashionItem } from "@/lib/mockData";

interface RentalPanelProps {
  item: MockFashionItem;
}

export default function RentalPanel({ item }: RentalPanelProps) {
  const { t } = useLanguage();
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includesCleaning, setIncludesCleaning] = useState(true);

  const calculateDays = () => {
    if (!startDate || !endDate) return 0;
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diff = Math.ceil(
      (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)
    );
    return diff > 0 ? diff : 0;
  };

  const days = calculateDays();
  const rentalTotal = days * (item.rentalPricePerDay || 0);
  const cleaningTotal = includesCleaning && item.cleaningFee ? item.cleaningFee : 0;
  const serviceFee = Math.round(rentalTotal * 0.05 * 100) / 100;
  const grandTotal = rentalTotal + cleaningTotal + serviceFee;

  return (
    <div className="card-light p-5 space-y-5">
      <div className="flex items-center gap-2 mb-1">
        <Calendar className="w-5 h-5 text-fashion-gold" />
        <h3 className="text-text-primary font-semibold text-lg">
          {t("selectDates")}
        </h3>
      </div>

      {/* Date inputs */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-text-muted text-xs mb-1 block">
            {t("startDate")}
          </label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="input-field text-sm"
            min={new Date().toISOString().split("T")[0]}
          />
        </div>
        <div>
          <label className="text-text-muted text-xs mb-1 block">
            {t("endDate")}
          </label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="input-field text-sm"
            min={startDate || new Date().toISOString().split("T")[0]}
          />
        </div>
      </div>

      {/* Cleaning option */}
      {item.cleaningFee && (
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={includesCleaning}
            onChange={(e) => setIncludesCleaning(e.target.checked)}
            className="w-4 h-4 rounded border-dark-border text-fashion-gold focus:ring-fashion-gold"
          />
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-fashion-gold" />
            <span className="text-text-secondary text-sm">
              {t("cleaningFee")} ({item.cleaningFee} {t("kwd")})
            </span>
          </div>
        </label>
      )}

      {/* Price breakdown */}
      {days > 0 && (
        <div className="space-y-2 border-t border-dark-border pt-4">
          <div className="flex justify-between text-sm">
            <span className="text-text-muted">
              {item.rentalPricePerDay} {t("kwd")} × {days} {t("days")}
            </span>
            <span className="text-text-secondary">
              {rentalTotal} {t("kwd")}
            </span>
          </div>
          {cleaningTotal > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">{t("cleaningFee")}</span>
              <span className="text-text-secondary">
                {cleaningTotal} {t("kwd")}
              </span>
            </div>
          )}
          <div className="flex justify-between text-sm">
            <span className="text-text-muted">{t("serviceFee")}</span>
            <span className="text-text-secondary">
              {serviceFee} {t("kwd")}
            </span>
          </div>
          <div className="flex justify-between font-bold text-lg border-t border-dark-border pt-2">
            <span className="text-text-primary">{t("total")}</span>
            <span className="text-fashion-gold">
              {grandTotal} {t("kwd")}
            </span>
          </div>
        </div>
      )}

      {/* Book button */}
      <button
        className="btn-solid w-full text-center disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={days === 0}
      >
        {t("bookNow")}
      </button>

      {/* Trust badge */}
      <div className="flex items-center gap-2 text-text-muted text-xs justify-center">
        <Shield className="w-3.5 h-3.5" />
        <span>
          {t("serviceFee")} 5% —
          {" "}حماية المستأجرة والمؤجرة
        </span>
      </div>
    </div>
  );
}
