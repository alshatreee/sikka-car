"use client";

import Link from "next/link";
import { useLanguage } from "@/components/shared/LanguageProvider";
import {
  Search,
  CalendarCheck,
  Truck,
  RotateCcw,
  ShieldCheck,
  CreditCard,
  HelpCircle,
  ArrowLeft,
  ArrowRight,
  Crown,
} from "lucide-react";

export default function HowItWorksPage() {
  const { isRTL } = useLanguage();
  const Arrow = isRTL ? ArrowLeft : ArrowRight;

  const rentalSteps = [
    {
      icon: Search,
      title: isRTL ? "تصفحي واختاري" : "Browse & Choose",
      desc: isRTL
        ? "تصفحي مئات القطع المصممة حسب المناسبة، المقاس، أو الماركة"
        : "Browse hundreds of designer pieces by occasion, size, or brand",
    },
    {
      icon: CalendarCheck,
      title: isRTL ? "حددي التواريخ واحجزي" : "Select Dates & Book",
      desc: isRTL
        ? "اختاري تواريخ التأجير ونوع التسليم — الحجز فوري"
        : "Pick rental dates and delivery type — instant booking",
    },
    {
      icon: Truck,
      title: isRTL ? "استلمي القطعة" : "Receive Your Piece",
      desc: isRTL
        ? "توصيل لباب بيتك أو استلام شخصي — القطعة نظيفة وجاهزة"
        : "Home delivery or pickup — cleaned and ready to wear",
    },
    {
      icon: RotateCcw,
      title: isRTL ? "ارجعيها بعد المناسبة" : "Return After Event",
      desc: isRTL
        ? "ارجعي القطعة في الموعد — نحن نتولى التنظيف"
        : "Return on time — we handle the cleaning",
    },
  ];

  const buySteps = [
    {
      icon: Search,
      title: isRTL ? "تصفحي المعروض" : "Browse Available",
      desc: isRTL
        ? "كل قطعة موصوفة بالتفصيل مع صور حقيقية وقياسات"
        : "Every piece has detailed descriptions, real photos, and measurements",
    },
    {
      icon: ShieldCheck,
      title: isRTL ? "تأكدي من التوثيق" : "Verify Authenticity",
      desc: isRTL
        ? "كل قطعة فاخرة موثقة — نتحقق من الماركة والحالة"
        : "Every luxury piece is verified — we check brand and condition",
    },
    {
      icon: CreditCard,
      title: isRTL ? "ادفعي بأمان" : "Pay Securely",
      desc: isRTL
        ? "دفع آمن عبر المنصة — أموالك محمية حتى الاستلام"
        : "Secure payment — your money is protected until delivery",
    },
    {
      icon: Truck,
      title: isRTL ? "استلمي وتأكدي" : "Receive & Verify",
      desc: isRTL
        ? "24 ساعة للتأكد من القطعة — استرجاع كامل إذا لم تطابق الوصف"
        : "24h to verify — full refund if not as described",
    },
  ];

  const faqs = [
    {
      q: isRTL ? "هل الملابس المؤجرة نظيفة؟" : "Are rented clothes clean?",
      a: isRTL
        ? "نعم، كل قطعة تُنظَّف احترافياً بعد كل استخدام. نتعاون مع أفضل مغاسل الكويت ونوفر شهادة تنظيف مع كل قطعة."
        : "Yes, every piece is professionally cleaned after each use. We partner with Kuwait's best laundries and provide a cleaning certificate.",
    },
    {
      q: isRTL ? "ماذا لو تلفت القطعة أثناء الاستخدام؟" : "What if the item gets damaged?",
      a: isRTL
        ? "البقع البسيطة والتآكل الطبيعي متوقع ومقبول. أما التلف الكبير فيتحمل المستأجر تكلفة الإصلاح أو قيمة القطعة حسب تقييم الحالة."
        : "Minor stains and normal wear are expected. Major damage requires the renter to cover repair costs or item value.",
    },
    {
      q: isRTL ? "كيف أتأكد من المقاس المناسب؟" : "How do I ensure the right fit?",
      a: isRTL
        ? "كل قطعة فيها قياسات تفصيلية (صدر، خصر، طول). يمكنك التواصل مع المالكة مباشرة للاستفسار. ننصح بقياس قطعة مشابهة عندك."
        : "Every item has detailed measurements (bust, waist, length). You can message the owner directly. We recommend measuring a similar piece you own.",
    },
    {
      q: isRTL ? "هل يمكنني تأجير ملابسي على المنصة؟" : "Can I rent out my own clothes?",
      a: isRTL
        ? "بالتأكيد! اضغطي على 'أضيفي قطعة'، ارفعي الصور، حددي السعر ونوع العرض (تأجير أو بيع أو كلاهما). فريقنا يراجع القطعة خلال 24 ساعة."
        : "Absolutely! Click 'List Item', upload photos, set price and listing type. Our team reviews within 24 hours.",
    },
    {
      q: isRTL ? "كم العمولة؟" : "What are the fees?",
      a: isRTL
        ? "عمولة التأجير 25% من سعر التأجير، وعمولة البيع 15% من سعر البيع. رسوم الخدمة 5% على المستأجرة/المشترية."
        : "Rental commission is 25% of rental price. Sale commission is 15% of sale price. 5% service fee on renter/buyer.",
    },
    {
      q: isRTL ? "هل تأجير الملابس حلال؟" : "Is clothing rental permissible in Islam?",
      a: isRTL
        ? "نعم، لا يوجد أي تحريم شرعي لارتداء ملابس مستأجرة أو مستعارة. الغسل يُطهّر أي ثوب، وقد ورد في السنة النبوية تشجيع على استعارة الملابس."
        : "Yes, there is no religious prohibition. Washing purifies any garment, and borrowing clothes is encouraged in prophetic tradition.",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 mb-4">
          <Crown className="w-8 h-8 text-fashion-gold" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-text-primary mb-3">
          {isRTL ? "كيف تعمل خزانة؟" : "How Does Khizana Work?"}
        </h1>
        <p className="text-text-muted text-lg">
          {isRTL
            ? "منصة بسيطة وآمنة لتأجير وبيع الأزياء المصممة"
            : "A simple and safe platform for designer fashion rental & sale"}
        </p>
      </div>

      {/* Rental Steps */}
      <div className="mb-16">
        <h2 className="text-xl font-bold text-fashion-gold mb-6 flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg bg-fashion-gold/10 flex items-center justify-center text-sm">1</span>
          {isRTL ? "التأجير — كيف تستأجرين" : "Renting — How to Rent"}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rentalSteps.map((step, i) => (
            <div key={i} className="card-light p-5 flex gap-4">
              <div className="w-12 h-12 rounded-xl bg-fashion-gold/10 flex items-center justify-center flex-shrink-0">
                <step.icon className="w-6 h-6 text-fashion-gold" />
              </div>
              <div>
                <h3 className="text-text-primary font-semibold text-sm mb-1">
                  {step.title}
                </h3>
                <p className="text-text-muted text-xs leading-relaxed">
                  {step.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Buy Steps */}
      <div className="mb-16">
        <h2 className="text-xl font-bold text-fashion-rose-light mb-6 flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg bg-fashion-rose/10 flex items-center justify-center text-sm">2</span>
          {isRTL ? "الشراء — كيف تشترين" : "Buying — How to Buy"}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {buySteps.map((step, i) => (
            <div key={i} className="card-light p-5 flex gap-4">
              <div className="w-12 h-12 rounded-xl bg-fashion-rose/10 flex items-center justify-center flex-shrink-0">
                <step.icon className="w-6 h-6 text-fashion-rose-light" />
              </div>
              <div>
                <h3 className="text-text-primary font-semibold text-sm mb-1">
                  {step.title}
                </h3>
                <p className="text-text-muted text-xs leading-relaxed">
                  {step.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* FAQ */}
      <div className="mb-16">
        <h2 className="text-xl font-bold text-text-primary mb-6 flex items-center gap-2">
          <HelpCircle className="w-6 h-6 text-fashion-gold" />
          {isRTL ? "أسئلة شائعة" : "FAQ"}
        </h2>
        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <details
              key={i}
              className="card-light group"
            >
              <summary className="p-4 cursor-pointer text-text-primary font-medium text-sm flex items-center justify-between list-none">
                {faq.q}
                <Arrow className="w-4 h-4 text-text-muted group-open:rotate-90 transition-transform" />
              </summary>
              <div className="px-4 pb-4 text-text-muted text-sm leading-relaxed border-t border-dark-border pt-3 mt-0">
                {faq.a}
              </div>
            </details>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="text-center">
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/rent" className="btn-solid flex items-center gap-2 justify-center">
            {isRTL ? "تصفحي التأجير" : "Browse Rentals"}
            <Arrow className="w-4 h-4" />
          </Link>
          <Link href="/buy" className="btn-secondary flex items-center gap-2 justify-center">
            {isRTL ? "تصفحي البيع" : "Browse Sales"}
            <Arrow className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
