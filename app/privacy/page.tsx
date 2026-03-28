'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { Shield } from 'lucide-react'

export default function PrivacyPage() {
  const { lang } = useLanguage()

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-card border border-dark-border">
            <Shield className="h-8 w-8 text-status-star" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'سياسة الخصوصية' : 'Privacy Policy'}
          </h1>
        </div>

        <div className="rounded-2xl border border-dark-border bg-dark-card p-6 space-y-6 text-sm text-text-secondary leading-relaxed">
          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '1. البيانات التي نجمعها' : '1. Data We Collect'}
            </h2>
            <ul className="list-disc ps-5 space-y-1">
              <li>{lang === 'ar' ? 'الاسم الكامل والبريد الإلكتروني ورقم الهاتف' : 'Full name, email, and phone number'}</li>
              <li>{lang === 'ar' ? 'الرقم المدني ورقم رخصة القيادة' : 'Civil ID and driving license number'}</li>
              <li>{lang === 'ar' ? 'صور السيارة ومستندات التسجيل' : 'Car photos and registration documents'}</li>
              <li>{lang === 'ar' ? 'تفاصيل الحجز والدفع' : 'Booking and payment details'}</li>
              <li>{lang === 'ar' ? 'صور التسليم والإرجاع' : 'Delivery and return photos'}</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '2. كيف نستخدم بياناتك' : '2. How We Use Your Data'}
            </h2>
            <ul className="list-disc ps-5 space-y-1">
              <li>{lang === 'ar' ? 'إدارة حسابك وتسهيل عمليات الحجز' : 'Managing your account and facilitating bookings'}</li>
              <li>{lang === 'ar' ? 'التحقق من هويتك وأهليتك للقيادة' : 'Verifying your identity and driving eligibility'}</li>
              <li>{lang === 'ar' ? 'التواصل معك بخصوص حجوزاتك' : 'Communicating with you about your bookings'}</li>
              <li>{lang === 'ar' ? 'حل النزاعات وتوثيق حالة السيارة' : 'Resolving disputes and documenting car condition'}</li>
              <li>{lang === 'ar' ? 'تحسين خدماتنا وتجربة المستخدم' : 'Improving our services and user experience'}</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '3. حماية البيانات' : '3. Data Protection'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'نستخدم تقنيات تشفير متقدمة لحماية بياناتك. لا نشارك معلوماتك الشخصية مع أطراف ثالثة إلا بموافقتك أو حسب متطلبات القانون.'
                : 'We use advanced encryption technologies to protect your data. We do not share your personal information with third parties without your consent or as required by law.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '4. حقوقك' : '4. Your Rights'}
            </h2>
            <ul className="list-disc ps-5 space-y-1">
              <li>{lang === 'ar' ? 'الوصول إلى بياناتك الشخصية' : 'Access your personal data'}</li>
              <li>{lang === 'ar' ? 'تصحيح أو تحديث بياناتك' : 'Correct or update your data'}</li>
              <li>{lang === 'ar' ? 'طلب حذف حسابك وبياناتك' : 'Request deletion of your account and data'}</li>
              <li>{lang === 'ar' ? 'الاعتراض على معالجة بياناتك' : 'Object to processing of your data'}</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '5. التواصل' : '5. Contact'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'لأي استفسار بخصوص الخصوصية، تواصل معنا عبر: support@sikkacar.com'
                : 'For any privacy inquiries, contact us at: support@sikkacar.com'}
            </p>
          </section>

          <p className="text-xs text-text-muted pt-4 border-t border-dark-border">
            {lang === 'ar' ? 'آخر تحديث: مارس 2026' : 'Last updated: March 2026'}
          </p>
        </div>
      </div>
    </main>
  )
}
