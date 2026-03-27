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
        <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-green-500/10 border border-green-500/20">
          <CheckCircle className="h-12 w-12 text-green-400" />
        </div>

        <h1 className="mb-3 text-3xl font-bold text-text-primary">
          {t('paymentSuccess')}
        </h1>
        <p className="mb-2 text-text-secondary">{t('paymentSuccessMsg')}</p>

        {bookingId && (
          <p className="mb-8 text-sm text-text-muted">
            {lang === 'ar' ? 'رقم الحجز: ' : 'Booking ID: '}
            <span className="font-mono">{bookingId}</span>
          </p>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="flex items-center justify-center gap-2 rounded-xl bg-brand-solid px-6 py-3 font-medium text-text-primary transition-all hover:bg-brand-solid-hover"
          >
            <Calendar className="h-4 w-4" />
            {t('viewBookings')}
          </Link>
          <Link
            href="/"
            className="flex items-center justify-center gap-2 rounded-xl border border-dark-border bg-dark-card px-6 py-3 font-medium text-text-primary transition-all hover:bg-dark-surface"
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
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-status-star border-t-transparent" />
        </div>
      }
    >
      <PaymentSuccessContent />
    </Suspense>
  )
}
