'use client'

import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { CheckCircle, Home, Calendar, AlertCircle, Loader2 } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { verifyPayment } from '@/actions/paymentActions'

type VerificationStatus = 'verifying' | 'success' | 'failed'

function PaymentSuccessContent() {
  const { t, lang } = useLanguage()
  const searchParams = useSearchParams()
  const bookingId = searchParams.get('bookingId')
  const tapId = searchParams.get('tap_id')

  const [status, setStatus] = useState<VerificationStatus>('verifying')
  const [error, setError] = useState<string | null>(null)
  const [isRetrying, setIsRetrying] = useState(false)

  useEffect(() => {
    const verifyPaymentStatus = async () => {
      if (!bookingId || !tapId) {
        setStatus('failed')
        setError(lang === 'ar' ? 'معلومات الدفع غير كاملة' : 'Payment information is incomplete')
        return
      }

      try {
        setStatus('verifying')
        setError(null)
        const result = await verifyPayment(bookingId, tapId)

        if (result.success) {
          setStatus('success')
        } else {
          setStatus('failed')
          setError(result.error || (lang === 'ar' ? 'فشل التحقق من الدفع' : 'Payment verification failed'))
        }
      } catch (err) {
        setStatus('failed')
        setError(lang === 'ar' ? 'حدث خطأ أثناء التحقق من الدفع' : 'An error occurred during payment verification')
      }
    }

    verifyPaymentStatus()
  }, [bookingId, tapId, lang])

  const handleRetry = async () => {
    if (!bookingId || !tapId) return

    setIsRetrying(true)
    try {
      setStatus('verifying')
      setError(null)
      const result = await verifyPayment(bookingId, tapId)

      if (result.success) {
        setStatus('success')
      } else {
        setStatus('failed')
        setError(result.error || (lang === 'ar' ? 'فشل التحقق من الدفع' : 'Payment verification failed'))
      }
    } catch (err) {
      setStatus('failed')
      setError(lang === 'ar' ? 'حدث خطأ أثناء التحقق من الدفع' : 'An error occurred during payment verification')
    } finally {
      setIsRetrying(false)
    }
  }

  if (status === 'verifying') {
    return (
      <main className="flex min-h-[80vh] items-center justify-center px-4">
        <div className="mx-auto max-w-md text-center">
          <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-brand-solid/10 border border-brand-solid/20">
            <Loader2 className="h-12 w-12 text-brand-solid animate-spin" />
          </div>

          <h1 className="mb-3 text-3xl font-bold text-text-primary">
            {t('verifyingPayment')}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar' ? 'يرجى الانتظار...' : 'Please wait...'}
          </p>

          {bookingId && (
            <p className="mt-8 text-sm text-text-muted">
              {lang === 'ar' ? 'رقم الحجز: ' : 'Booking ID: '}
              <span className="font-mono">{bookingId}</span>
            </p>
          )}
        </div>
      </main>
    )
  }

  if (status === 'failed') {
    return (
      <main className="flex min-h-[80vh] items-center justify-center px-4">
        <div className="mx-auto max-w-md text-center">
          <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-red-500/10 border border-red-500/20">
            <AlertCircle className="h-12 w-12 text-red-400" />
          </div>

          <h1 className="mb-3 text-3xl font-bold text-text-primary">
            {t('paymentFailed')}
          </h1>
          <p className="mb-2 text-text-secondary">{t('paymentFailedMsg')}</p>

          {error && (
            <p className="mb-6 text-sm text-red-400">
              {error}
            </p>
          )}

          {bookingId && (
            <p className="mb-8 text-sm text-text-muted">
              {lang === 'ar' ? 'رقم الحجز: ' : 'Booking ID: '}
              <span className="font-mono">{bookingId}</span>
            </p>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="flex items-center justify-center gap-2 rounded-xl bg-brand-solid px-6 py-3 font-medium text-text-primary transition-all hover:bg-brand-solid-hover disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRetrying ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {lang === 'ar' ? 'جاري المحاولة...' : 'Retrying...'}
                </>
              ) : (
                <>
                  <Calendar className="h-4 w-4" />
                  {t('retryPayment')}
                </>
              )}
            </button>
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
