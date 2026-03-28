'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { FileText } from 'lucide-react'

export default function TermsPage() {
  const { lang } = useLanguage()

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-card border border-dark-border">
            <FileText className="h-8 w-8 text-status-star" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'شروط الاستخدام' : 'Terms of Service'}
          </h1>
        </div>

        <div className="rounded-2xl border border-dark-border bg-dark-card p-6 space-y-6 text-sm text-text-secondary leading-relaxed">
          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '1. مقدمة' : '1. Introduction'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'مرحبًا بك في سكة كار. باستخدامك لمنصتنا، فإنك توافق على هذه الشروط والأحكام. سكة كار هي منصة إلكترونية تربط ملاك السيارات بالمستأجرين في دولة الكويت.'
                : 'Welcome to Sikka Car. By using our platform, you agree to these terms and conditions. Sikka Car is an online platform connecting car owners with renters in Kuwait.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '2. الأهلية' : '2. Eligibility'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'يجب أن يكون عمرك 21 سنة أو أكثر لاستخدام خدمات التأجير. يجب أن تمتلك رخصة قيادة سارية المفعول ورقم مدني كويتي.'
                : 'You must be 21 years or older to use rental services. You must have a valid driving license and Kuwaiti civil ID.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '3. الحجز والدفع' : '3. Booking & Payment'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'عند إتمام الحجز والدفع، يُنشأ عقد بينك وبين مالك السيارة. المبلغ يُدفع مقدمًا عبر بوابة الدفع الإلكتروني. سكة كار ليست طرفًا في العقد وإنما وسيط تقني.'
                : 'When you complete a booking and payment, a contract is created between you and the car owner. Payment is made upfront via the electronic payment gateway. Sikka Car is a technical intermediary, not a party to the contract.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '4. مسؤولية المستأجر' : '4. Renter Responsibilities'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'المستأجر مسؤول عن السيارة خلال فترة الإيجار. يجب إعادة السيارة بنفس الحالة التي تم استلامها بها. أي أضرار أو مخالفات مرورية تقع على مسؤولية المستأجر.'
                : 'The renter is responsible for the car during the rental period. The car must be returned in the same condition it was received. Any damages or traffic violations are the renter\'s responsibility.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '5. مسؤولية مالك السيارة' : '5. Owner Responsibilities'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'مالك السيارة مسؤول عن تقديم سيارة صالحة للاستخدام ومطابقة للوصف المعلن. يجب أن تكون السيارة مؤمنة ومرخصة وفق القوانين الكويتية.'
                : 'The car owner is responsible for providing a roadworthy car that matches the listing. The car must be insured and licensed per Kuwaiti law.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '6. التصوير والتوثيق' : '6. Photography & Documentation'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'يلتزم صاحب السيارة بتصوير السيارة من الجهات الأربع عند التسليم. يلتزم المستأجر بتصوير السيارة عند الإرجاع. الصور تُحفظ في المنصة كمرجع لحالة السيارة.'
                : 'The owner must photograph the car from all 4 sides at delivery. The renter must photograph it at return. Photos are stored on the platform as a record of the car\'s condition.'}
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-bold text-text-primary">
              {lang === 'ar' ? '7. تعديل الشروط' : '7. Changes to Terms'}
            </h2>
            <p>
              {lang === 'ar'
                ? 'نحتفظ بحق تعديل هذه الشروط في أي وقت. سيتم إخطارك بالتغييرات الجوهرية عبر البريد الإلكتروني أو إشعار على المنصة.'
                : 'We reserve the right to modify these terms at any time. You will be notified of material changes via email or platform notification.'}
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
