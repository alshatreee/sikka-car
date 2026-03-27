'use client'

import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { X, Shield } from 'lucide-react'

interface LegalModalProps {
  type: 'terms' | 'privacy'
  isOpen: boolean
  onClose: () => void
}

export function LegalModal({ type, isOpen, onClose }: LegalModalProps) {
  const { t, lang } = useLanguage()

  if (!isOpen) return null

  const title = type === 'terms' ? t('termsOfService') : t('privacyPolicy')

  const termsContent =
    lang === 'ar'
      ? `شروط استخدام منصة سكة كار

1. المقدمة
مرحباً بكم في منصة سكة كار لتأجير السيارات بين الأفراد. باستخدامكم لهذه المنصة، فإنكم توافقون على الالتزام بهذه الشروط والأحكام.

2. الأهلية
يجب أن يكون عمر المستخدم 18 عاماً فأكثر لاستخدام المنصة. يجب أن يحمل المستأجر رخصة قيادة سارية المفعول.

3. مسؤولية المالك
يتحمل مالك السيارة مسؤولية التأكد من أن السيارة في حالة جيدة وآمنة للقيادة. يجب أن تكون جميع الوثائق والتراخيص سارية المفعول.

4. مسؤولية المستأجر
يتحمل المستأجر مسؤولية استخدام السيارة بشكل آمن ووفقاً لقوانين المرور. أي أضرار تحدث أثناء فترة الإيجار تكون مسؤولية المستأجر.

5. الدفع والإلغاء
يتم الدفع عبر بوابة الدفع الإلكترونية المعتمدة. سياسة الإلغاء تختلف حسب توقيت الإلغاء.`
      : `Sikka Car Terms of Service

1. Introduction
Welcome to Sikka Car, a peer-to-peer car rental platform. By using this platform, you agree to be bound by these terms and conditions.

2. Eligibility
Users must be 18 years or older. Renters must hold a valid driving license.

3. Owner Responsibility
Car owners are responsible for ensuring their vehicle is in good and safe condition. All documents and licenses must be valid.

4. Renter Responsibility
Renters are responsible for using the car safely and in accordance with traffic laws. Any damages during the rental period are the renter's responsibility.

5. Payment and Cancellation
Payments are processed through our approved payment gateway. Cancellation policies vary based on timing.`

  const privacyContent =
    lang === 'ar'
      ? `سياسة الخصوصية - سكة كار

1. جمع المعلومات
نقوم بجمع المعلومات الشخصية اللازمة لتقديم خدماتنا بما في ذلك: الاسم، البريد الإلكتروني، رقم الهاتف، ومعلومات الدفع.

2. استخدام المعلومات
نستخدم معلوماتكم لتسهيل عمليات التأجير، التواصل معكم، وتحسين خدماتنا.

3. حماية المعلومات
نستخدم تقنيات أمان متقدمة لحماية بياناتكم الشخصية.

4. مشاركة المعلومات
لا نشارك معلوماتكم الشخصية مع أطراف ثالثة إلا في الحالات المطلوبة قانونياً.`
      : `Sikka Car Privacy Policy

1. Information Collection
We collect personal information necessary to provide our services, including: name, email, phone number, and payment information.

2. Use of Information
We use your information to facilitate rental transactions, communicate with you, and improve our services.

3. Information Protection
We use advanced security technologies to protect your personal data.

4. Information Sharing
We do not share your personal information with third parties except where legally required.`

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary-500" />
            <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="whitespace-pre-line text-sm leading-relaxed text-gray-600">
          {type === 'terms' ? termsContent : privacyContent}
        </div>

        <button
          onClick={onClose}
          className="mt-6 w-full rounded-xl bg-primary-500 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600"
        >
          {lang === 'ar' ? 'فهمت' : 'I Understand'}
        </button>
      </div>
    </div>
  )
}

export function LegalLinks() {
  const { t } = useLanguage()
  const [modalType, setModalType] = useState<'terms' | 'privacy' | null>(null)

  return (
    <>
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <button
          onClick={() => setModalType('terms')}
          className="transition-colors hover:text-gray-300"
        >
          {t('termsOfService')}
        </button>
        <span>|</span>
        <button
          onClick={() => setModalType('privacy')}
          className="transition-colors hover:text-gray-300"
        >
          {t('privacyPolicy')}
        </button>
      </div>

      {modalType && (
        <LegalModal
          type={modalType}
          isOpen={true}
          onClose={() => setModalType(null)}
        />
      )}
    </>
  )
}
