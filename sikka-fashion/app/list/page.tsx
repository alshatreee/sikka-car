"use client";

import { useLanguage } from "@/components/shared/LanguageProvider";
import { PlusCircle, Upload } from "lucide-react";
import { useState } from "react";

const categories = ["SUIT", "BLAZER", "DRESS", "EVENING_GOWN", "ABAYA", "JUMPSUIT", "SKIRT_SET", "OTHER"];
const sizes = ["XS", "S", "M", "L", "XL", "XXL"];
const occasions = ["WEDDING", "FORMAL", "BUSINESS", "PARTY", "GRADUATION", "ENGAGEMENT", "EID", "NATIONAL_DAY", "OTHER"];
const conditions = ["NEW_WITH_TAGS", "EXCELLENT", "VERY_GOOD", "GOOD"];
const areas = ["العاصمة", "حولي", "السالمية", "الجابرية", "الشويخ", "المنقف", "الأحمدي", "الفروانية", "مبارك الكبير"];

export default function ListPage() {
  const { t } = useLanguage();
  const [listingType, setListingType] = useState("BOTH");

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-fashion-gold/10 flex items-center justify-center">
          <PlusCircle className="w-5 h-5 text-fashion-gold" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {t("addItem")}
          </h1>
          <p className="text-text-muted text-sm">
            شاركي أزياءك مع مجتمع خزانة
          </p>
        </div>
      </div>

      <form className="space-y-6">
        {/* Basic Info */}
        <div className="card-light p-5 space-y-4">
          <h2 className="text-text-primary font-semibold">المعلومات الأساسية</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemTitle")} (English)
              </label>
              <input type="text" className="input-field" placeholder="e.g. Taller Marmo Evening Dress" />
            </div>
            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemTitleAr")}
              </label>
              <input type="text" className="input-field" placeholder="مثال: فستان سهرة تالر مارمو" />
            </div>
          </div>

          <div>
            <label className="text-text-muted text-sm mb-1.5 block">
              {t("itemBrand")}
            </label>
            <input type="text" className="input-field" placeholder="e.g. Zara, Elie Saab, Meshki" />
          </div>

          <div>
            <label className="text-text-muted text-sm mb-1.5 block">
              {t("itemDescription")}
            </label>
            <textarea className="input-field min-h-[100px] resize-none" placeholder="وصف القطعة وتفاصيلها..." />
          </div>
        </div>

        {/* Details */}
        <div className="card-light p-5 space-y-4">
          <h2 className="text-text-primary font-semibold">التفاصيل</h2>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemCategory")}
              </label>
              <select className="input-field">
                {categories.map((cat) => (
                  <option key={cat} value={cat}>{t(cat as any)}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemSize")}
              </label>
              <select className="input-field">
                {sizes.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemColor")}
              </label>
              <input type="text" className="input-field" placeholder="أسود، أبيض، ذهبي..." />
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemCondition")}
              </label>
              <select className="input-field">
                {conditions.map((cond) => (
                  <option key={cond} value={cond}>{t(cond as any)}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("itemOccasion")}
              </label>
              <select className="input-field">
                {occasions.map((occ) => (
                  <option key={occ} value={occ}>{t(occ as any)}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("area")}
              </label>
              <select className="input-field">
                {areas.map((area) => (
                  <option key={area} value={area}>{area}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Pricing */}
        <div className="card-light p-5 space-y-4">
          <h2 className="text-text-primary font-semibold">التسعير</h2>

          {/* Listing Type */}
          <div>
            <label className="text-text-muted text-sm mb-2 block">
              {t("listingType")}
            </label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { value: "RENT", label: t("forRent"), color: "fashion-gold" },
                { value: "SALE", label: t("forSale"), color: "fashion-rose-light" },
                { value: "BOTH", label: t("forBoth"), color: "purple-400" },
              ].map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setListingType(type.value)}
                  className={`py-3 rounded-xl text-sm font-medium transition-all border ${
                    listingType === type.value
                      ? `border-${type.color} text-${type.color} bg-${type.color}/10`
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
              </div>
            )}

            {(listingType === "SALE" || listingType === "BOTH") && (
              <div>
                <label className="text-text-muted text-sm mb-1.5 block">
                  {t("salePriceLabel")} ({t("kwd")})
                </label>
                <input type="number" className="input-field" placeholder="0.000" />
              </div>
            )}
          </div>

          {(listingType === "RENT" || listingType === "BOTH") && (
            <div>
              <label className="text-text-muted text-sm mb-1.5 block">
                {t("cleaningFeeLabel")} ({t("kwd")})
              </label>
              <input type="number" className="input-field" placeholder="0.000" />
            </div>
          )}
        </div>

        {/* Images */}
        <div className="card-light p-5 space-y-4">
          <h2 className="text-text-primary font-semibold">{t("uploadImages")}</h2>
          <div className="border-2 border-dashed border-dark-border rounded-xl p-8 text-center hover:border-fashion-gold/50 transition-colors cursor-pointer">
            <Upload className="w-8 h-8 text-text-muted mx-auto mb-2" />
            <p className="text-text-muted text-sm">
              اسحبي الصور هنا أو اضغطي للرفع
            </p>
            <p className="text-text-muted text-xs mt-1">
              حتى 5 صور — JPG, PNG — حد أقصى 5MB لكل صورة
            </p>
          </div>
        </div>

        {/* Submit */}
        <button type="submit" className="btn-solid w-full text-center text-lg py-4">
          {t("submit")}
        </button>
      </form>
    </div>
  );
}
