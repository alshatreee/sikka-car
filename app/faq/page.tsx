'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { ChevronDown, HelpCircle } from 'lucide-react'
import { useState } from 'react'

const faqs = [
  {
    q: { ar: 'كيف أحجز سيارة؟', en: 'How do I book a car?' },
    a: { ar: 'تصفح السيارات المتاحة، اختر السيارة المناسبة، حدد التواريخ، وأكمل الدفع. ستحصل على تأكيد فوري.', en: 'Browse available cars, select one, choose your dates, and complete payment. You\'ll get instant confirmation.' },
  },
  {
    q: { ar: 'كيف أضيف سيارتي للإيجار؟', en: 'How do I list my car?' },
    a: { ar: 'سجل دخول، اضغط "أضف سيارتك"، أكمل البيانات والصور، وأرسلها للمراجعة. سيتم مراجعتها خلال 24 ساعة.', en: 'Sign in, click "List Your Car", fill in details and photos, and submit for review. It\'ll be reviewed within 24 hours.' },
  },
  {
    q: { ar: 'ما هي طرق الدفع المتاحة؟', en: 'What payment methods are available?' },
    a: { ar: 'نقبل الدفع عبر K-Net، Visa، Mastercard، و Apple Pay من خلال بوابة Tap للدفع الآمن.', en: 'We accept K-Net, Visa, Mastercard, and Apple Pay through Tap secure payment gateway.' },
  },
  {
    q: { ar: 'هل يمكنني إلغاء الحجز؟', en: 'Can I cancel a booking?' },
    a: { ar: 'نعم، يمكنك إلغاء الحجز من لوحة التحكم قبل بدء الإيجار. تطبق سياسة الإلغاء والاسترداد.', en: 'Yes, you can cancel from your dashboard before the rental starts. Cancellation and refund policies apply.' },
  },
  {
    q: { ar: 'ما المستندات المطلوبة للحجز؟', en: 'What documents are needed to book?' },
    a: { ar: 'تحتاج إلى: رقم مدني ساري، رخصة قيادة سارية. يمكنك إدخالها من صفحة الملف الشخصي.', en: 'You need a valid civil ID and driving license. You can enter them from your profile page.' },
  },
  {
    q: { ar: 'كيف يتم تسليم واستلام السيارة؟', en: 'How does delivery and return work?' },
    a: { ar: 'عند التسليم، يصوّر صاحب السيارة من الجهات الأربع. عند الإرجاع، يصوّر المستأجر السيارة. الصور محفوظة في الموقع لحماية الطرفين.', en: 'At delivery, the owner photographs the car from all 4 sides. At return, the renter photographs it. Photos are saved on the site to protect both parties.' },
  },
  {
    q: { ar: 'هل التأمين مشمول؟', en: 'Is insurance included?' },
    a: { ar: 'التأمين يعتمد على صاحب السيارة. يرجى التواصل مع المالك لمعرفة تفاصيل التأمين قبل الحجز.', en: 'Insurance depends on the car owner. Please contact the owner for insurance details before booking.' },
  },
  {
    q: { ar: 'كيف أتواصل مع صاحب السيارة؟', en: 'How do I contact the car owner?' },
    a: { ar: 'معلومات التواصل (الهاتف والبريد) متاحة في صفحة تفاصيل السيارة بعد تسجيل الدخول.', en: 'Contact info (phone and email) is available on the car detail page after signing in.' },
  },
]

export default function FaqPage() {
  const { lang } = useLanguage()
  const [open, setOpen] = useState<number | null>(null)

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-card border border-dark-border">
            <HelpCircle className="h-8 w-8 text-status-star" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'الأسئلة الشائعة' : 'FAQ'}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar' ? 'أجوبة على أكثر الأسئلة شيوعاً' : 'Answers to common questions'}
          </p>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <div
              key={i}
              className="rounded-2xl border border-dark-border bg-dark-card overflow-hidden"
            >
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="flex w-full items-center justify-between p-5 text-start"
              >
                <span className="font-medium text-text-primary">{faq.q[lang]}</span>
                <ChevronDown
                  className={`h-5 w-5 shrink-0 text-text-muted transition-transform ${
                    open === i ? 'rotate-180' : ''
                  }`}
                />
              </button>
              {open === i && (
                <div className="border-t border-dark-border px-5 py-4 text-sm text-text-secondary leading-relaxed">
                  {faq.a[lang]}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}
