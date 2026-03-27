'use client'

import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { CheckCircle, Home, Calendar } from 'lucide-react'
import { Suspense } from 'react'

function PaymentSuccessContent() {
  const { t, lang } = useLanguage()
  const searchParams = useSearchParams()
  const bookingId = searchParams.get('bookingId')

  return (
    <main className="flex min-h-[80vh] items-center justify-center px-4">
      <div className="mx-auto max-w-md text-center">
        <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-green-100">
          <CheckCircle className="h-12 w-12 text-green-500" />
        </div>

        <h1 className="mb-3 text-3xl font-bold text-gray-900">
          {t('paymentSuccess')}
        </h1>
        <p className="mb-2 text-gray-500">{t('paymentSuccessMsg')}</p>

        {bookingId && (
          <p className="mb-8 text-sm text-gray-400">
            {lang === 'ar' ? 'رقم الحجز: ' : 'Booking ID: '}
            <span className="font-mono">{bookingId}</span>
          </p>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="btn-primary flex items-center justify-center gap-2"
          >
            <Calendar className="h-4 w-4" />
            {t('viewBookings')}
          </Link>
          <Link
            href="/"
            className="btn-secondary flex items-center justify-center gap-2"
          >
            <Home className="h-4 w-4" />
            {t('backToHome')}
          </Link>
        </div>
      </div>
    </main>
  )
}

export default function PaymentSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[80vh] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
        </div>
      }
    >
      <PaymentSuccessContent />
    </Suspense>
  )
}
