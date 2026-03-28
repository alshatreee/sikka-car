"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import { PlusCircle, Upload, ArrowLeft, ArrowRight, Check } from "lucide-react";
import { useState } from "react";

const categories = ["SUIT", "BLAZER", "DRESS", "EVENING_GOWN", "ABAYA", "JUMPSUIT", "SKIRT_SET", "OTHER"];
const sizes = ["XS", "S", "M", "L", "XL", "XXL"];
const occasions = ["WEDDING", "FORMAL", "BUSINESS", "PARTY", "GRADUATION", "ENGAGEMENT", "EID", "NATIONAL_DAY", "OTHER"];
const conditions = ["NEW_WITH_TAGS", "EXCELLENT", "VERY_GOOD", "GOOD"];
const areas = ["العاصمة", "حولي", "السالمية", "الجابرية", "الشويخ", "المنقف", "الأحمدي", "الفروانية", "مبارك الكبير"];

const TOTAL_STEPS = 4;

export default function ListPage() {
  const { t, isRTL } = useLanguage();
  const [step, setStep] = useState(1);
  const [listingType, setListingType] = useState("BOTH");
  const BackArrow = isRTL ? ArrowRight : ArrowLeft;
  const NextArrow = isRTL ? ArrowLeft : ArrowRight;

  const stepLabels = [
    isRTL ? "معلومات القطعة" : "Item Info",
    isRTL ? "الحالة والتفاصيل" : "Details",
    isRTL ? "التسعير" : "Pricing",
    isRTL ? "الصور والمراجعة" : "Photos & Review",
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-fashion-gold/10 flex items-center justify-center">
          <PlusCircle className="w-5 h-5 text-fashion-gold" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t("addItem")}</h1>
          <p className="text-text-muted text-sm">
            {isRTL ? "شاركي أزياءك مع مجتمع خزانة" : "Share your fashion with the Khizana community"}
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          {stepLabels.map((label, i) => (
            <div key={i} className="flex flex-col items-center flex-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold mb-1 transition-all ${
                  step > i + 1
                    ? "bg-status-success text-white"
                    : step === i + 1
                    ? "bg-fashion-gold text-dark-bg"
                    : "bg-dark-surface text-text-muted"
                }`}
              >
                {step > i + 1 ? <Check className="w-4 h-4" /> : i + 1}
              </div>
              <span
                className={`text-[10px] text-center hidden sm:block ${
                  step === i + 1 ? "text-fashion-gold font-medium" : "text-text-muted"
                }`}
              >
                {label}
              </span>
            </div>
          ))}
        </div>
        <div className="w-full bg-dark-surface rounded-full h-1.5">
          <div
            className="bg-fashion-gold h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </div>

      <form onSubmit={(e) => e.preventDefault()}>
        {/* Step 1: Basic Info */}
        {step === 1 && (
          <div className="card-light p-5 space-y-4 animate-in">
            <h2 className="text-text-primary font-semibold">
              {isRTL ? "المعلومات الأساسية" : "Basic Info"}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">
                  {t("itemTitle")} (English)
                </label>
                <input type="text" className="input-field" placeholder="e.g. Taller Marmo Evening Dress" />
              </div>
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("itemTitleAr")}</label>
                <input type="text" className="input-field" placeholder="مثال: فستان سهرة تالر مارمو" />
              </div>
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">{t("itemBrand")}</label>
              <input type="text" className="input-field" placeholder="e.g. Zara, Elie Saab, Meshki" />
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">{t("itemDescription")}</label>
              <textarea className="input-field min-h-[100px] resize-none" placeholder={isRTL ? "وصف القطعة وتفاصيلها..." : "Describe the item..."} />
            </div>
          </div>
        )}

        {/* Step 2: Details */}
        {step === 2 && (
          <div className="card-light p-5 space-y-4 animate-in">
            <h2 className="text-text-primary font-semibold">
              {isRTL ? "التفاصيل" : "Details"}
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("itemCategory")}</label>
                <select className="input-field">
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>{t(cat as any)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("itemSize")}</label>
                <select className="input-field">
                  {sizes.map((size) => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("itemColor")}</label>
                <input type="text" className="input-field" placeholder={isRTL ? "أسود، أبيض، ذهبي..." : "Black, White, Gold..."} />
              </div>
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("itemCondition")}</label>
                <select className="input-field">
                  {conditions.map((cond) => (
                    <option key={cond} value={cond}>{t(cond as any)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("itemOccasion")}</label>
                <select className="input-field">
                  {occasions.map((occ) => (
                    <option key={occ} value={occ}>{t(occ as any)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">{t("area")}</label>
                <select className="input-field">
                  {areas.map((area) => (
                    <option key={area} value={area}>{area}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Measurements */}
            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {isRTL ? "القياسات (اختياري)" : "Measurements (Optional)"}
              </label>
              <div className="grid grid-cols-3 gap-3">
                <input type="text" className="input-field text-sm" placeholder={isRTL ? "الصدر (سم)" : "Bust (cm)"} />
                <input type="text" className="input-field text-sm" placeholder={isRTL ? "الخصر (سم)" : "Waist (cm)"} />
                <input type="text" className="input-field text-sm" placeholder={isRTL ? "الطول (سم)" : "Length (cm)"} />
              </div>
            </div>

            <div className="bg-dark-surface/50 rounded-xl p-3 text-xs text-text-muted flex items-start gap-2">
              <span className="text-fashion-gold">💡</span>
              {isRTL
                ? "إضافة القياسات تزيد احتمال الحجز بـ 40% — المستأجرة تحتاج تعرف المقاس بالضبط"
                : "Adding measurements increases booking by 40% — renters need exact sizing"}
            </div>
          </div>
        )}

        {/* Step 3: Pricing */}
        {step === 3 && (
          <div className="card-light p-5 space-y-4 animate-in">
            <h2 className="text-text-primary font-semibold">
              {isRTL ? "التسعير" : "Pricing"}
            </h2>

            {/* Listing Type */}
            <div>
              <label className="text-text-muted text-sm mb-2 block">{t("listingType")}</label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { value: "RENT", label: t("forRent"), active: "border-fashion-gold text-fashion-gold bg-fashion-gold/10" },
                  { value: "SALE", label: t("forSale"), active: "border-fashion-rose-light text-fashion-rose-light bg-fashion-rose/10" },
                  { value: "BOTH", label: t("forBoth"), active: "border-purple-400 text-purple-400 bg-purple-500/10" },
                ].map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setListingType(type.value)}
                    className={`py-3 rounded-xl text-sm font-medium transition-all border ${
                      listingType === type.value
                        ? type.active
                        : "border-dark-border text-text-muted hover:border-dark-surface"
                    }`}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemRetailPrice")} ({t("kwd")})
              </label>
              <input type="number" className="input-field" placeholder="0.000" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(listingType === "RENT" || listingType === "BOTH") && (
                <div>
                  <label className="text-text-muted text-sm mb-1.5 block">
                    {t("rentalPricePerDay")} ({t("kwd")})
                  </label>
                  <input type="number" className="input-field" placeholder="0.000" />
                  <p className="text-text-muted text-xs mt-1">
                    💡 {isRTL ? "السعر المقترح: 10-15% من سعر التجزئة" : "Suggested: 10-15% of retail price"}
                  </p>
                </div>
              )}
              {(listingType === "SALE" || listingType === "BOTH") && (
                <div>
                  <label className="text-text-muted text-sm mb-1.5 block">
                    {t("salePriceLabel")} ({t("kwd")})
                  </label>
                  <input type="number" className="input-field" placeholder="0.000" />
                  <p className="text-text-muted text-xs mt-1">
                    💡 {isRTL ? "السعر المقترح: 40-60% من سعر التجزئة" : "Suggested: 40-60% of retail price"}
                  </p>
                </div>
              )}
            </div>

            {(listingType === "RENT" || listingType === "BOTH") && (
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">
                  {t("cleaningFeeLabel")} ({t("kwd")})
                </label>
                <input type="number" className="input-field" placeholder="3-8 د.ك" />
              </div>
            )}
          </div>
        )}

        {/* Step 4: Photos & Review */}
        {step === 4 && (
          <div className="space-y-4 animate-in">
            <div className="card-light p-5 space-y-4">
              <h2 className="text-text-primary font-semibold">{t("uploadImages")}</h2>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: isRTL ? "أمامي *" : "Front *", required: true },
                  { label: isRTL ? "جانبي" : "Side", required: false },
                  { label: isRTL ? "خلفي" : "Back", required: false },
                  { label: isRTL ? "تفاصيل/تاغ" : "Detail/Tag", required: false },
                ].map((slot, i) => (
                  <div
                    key={i}
                    className={`aspect-[3/4] border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors ${
                      slot.required
                        ? "border-fashion-gold/40 hover:border-fashion-gold bg-fashion-gold/5"
                        : "border-dark-border hover:border-fashion-gold/50"
                    }`}
                  >
                    <Upload className="w-6 h-6 text-text-muted mb-1" />
                    <span className="text-text-muted text-xs">{slot.label}</span>
                  </div>
                ))}
              </div>

              <p className="text-text-muted text-xs">
                {isRTL
                  ? "صورة أمامية إلزامية — حتى 5 صور — JPG, PNG — حد أقصى 5MB"
                  : "Front photo required — up to 5 photos — JPG, PNG — max 5MB each"}
              </p>
            </div>

            {/* Review Summary */}
            <div className="card-light p-5 space-y-3">
              <h2 className="text-text-primary font-semibold">
                {isRTL ? "مراجعة قبل النشر" : "Review Before Publishing"}
              </h2>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  { label: isRTL ? "النوع" : "Type", value: listingType === "RENT" ? t("forRent") : listingType === "SALE" ? t("forSale") : t("forBoth") },
                  { label: isRTL ? "العمولة" : "Commission", value: listingType === "SALE" ? "15%" : "25%" },
                ].map((item, i) => (
                  <div key={i} className="flex justify-between">
                    <span className="text-text-muted">{item.label}</span>
                    <span className="text-text-primary font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
              <p className="text-text-muted text-xs border-t border-dark-border pt-3">
                {isRTL
                  ? "بعد النشر، فريقنا يراجع القطعة خلال 24 ساعة ويوافق عليها أو يطلب تعديلات."
                  : "After publishing, our team reviews within 24 hours and approves or requests changes."}
              </p>
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between mt-6">
          {step > 1 ? (
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              className="flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors text-sm"
            >
              <BackArrow className="w-4 h-4" />
              {isRTL ? "السابق" : "Previous"}
            </button>
          ) : (
            <div />
          )}

          {step < TOTAL_STEPS ? (
            <button
              type="button"
              onClick={() => setStep(step + 1)}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              {isRTL ? "التالي" : "Next"}
              <NextArrow className="w-4 h-4" />
            </button>
          ) : (
            <button type="submit" className="btn-solid flex items-center gap-2 text-sm">
              {t("submit")}
              <Check className="w-4 h-4" />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
