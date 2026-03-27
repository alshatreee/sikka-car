'use client'

import { useState, useTransition, useMemo } from 'react'
import { createBooking } from '@/actions/bookingActions'
import { initiatePayment } from '@/actions/paymentActions'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Calendar, Clock, FileText, CreditCard } from 'lucide-react'

interface BookingPanelProps {
  carId: string
  dailyPrice: number
  customerName: string
  customerEmail: string
}

export function BookingPanel({
  carId,
  dailyPrice,
  customerName,
  customerEmail,
}: BookingPanelProps) {
  const { t } = useLanguage()
  const [pending, startTransition] = useTransition()
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [pickupTime, setPickupTime] = useState('')
  const [dropoffTime, setDropoffTime] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')

  const totalDays = useMemo(() => {
    if (!startDate || !endDate) return 0
    const start = new Date(startDate)
    const end = new Date(endDate)
    const diff = Math.ceil(
      (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)
    )
    return diff > 0 ? diff : 0
  }, [startDate, endDate])

  const totalAmount = totalDays * dailyPrice

  function handleBooking() {
    setError('')

    if (!startDate || !endDate) {
      setError('يرجى تحديد تواريخ الحجز')
      return
    }

    if (totalDays <= 0) {
      setError('تاريخ النهاية يجب أن يكون بعد تاريخ البداية')
      return
    }

    startTransition(async () => {
      const bookingResult = await createBooking({
        carId,
        startDate,
        endDate,
        pickupTime,
        dropoffTime,
        notes,
      })

      if (!bookingResult.success || !bookingResult.bookingId) {
        setError(
          bookingResult.error || 'حدث خطأ أثناء إنشاء الحجز'
        )
        return
      }

      const paymentResult = await initiatePayment(
        bookingResult.totalAmount,
        bookingResult.bookingId,
        customerName,
        customerEmail
      )

      if (paymentResult.success && paymentResult.checkoutUrl) {
        window.location.href = paymentResult.checkoutUrl
      } else {
        setError(paymentResult.error || 'فشل إنشاء رابط الدفع')
      }
    })
  }

  return (
    <div className="rounded-2xl border border-dark-border bg-dark-card p-6 shadow-lg">
      <h3 className="mb-4 text-lg font-bold text-text-primary">
        {t('bookNow')}
      </h3>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
              <Calendar className="h-3.5 w-3.5 text-text-secondary" />
              {t('startDate')}
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              min={new Date().toISOString().split('T')[0]}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
          <div>
            <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
              <Calendar className="h-3.5 w-3.5 text-text-secondary" />
              {t('endDate')}
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate || new Date().toISOString().split('T')[0]}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
              <Clock className="h-3.5 w-3.5 text-text-secondary" />
              {t('pickupTime')}
            </label>
            <input
              type="time"
              value={pickupTime}
              onChange={(e) => setPickupTime(e.target.value)}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
          <div>
            <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
              <Clock className="h-3.5 w-3.5 text-text-secondary" />
              {t('dropoffTime')}
            </label>
            <input
              type="time"
              value={dropoffTime}
              onChange={(e) => setDropoffTime(e.target.value)}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
            <FileText className="h-3.5 w-3.5 text-text-secondary" />
            {t('additionalNotes')}
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t('additionalNotes')}
            rows={2}
            className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
          />
        </div>

        {/* Price Summary */}
        {totalDays > 0 && (
          <div className="rounded-xl bg-dark-surface p-4 border border-dark-border">
            <div className="flex items-center justify-between text-sm text-text-secondary">
              <span>
                {dailyPrice} {t('perDay')} × {totalDays}{' '}
                {totalDays === 1 ? 'يوم' : 'أيام'}
              </span>
              <span className="text-lg font-bold text-status-star">
                {totalAmount.toFixed(2)} د.ك
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-xl bg-status-warning/10 p-3 text-sm text-status-warning border border-status-warning/20">
            {error}
          </div>
        )}

        <button
          onClick={handleBooking}
          disabled={pending || totalDays <= 0}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CreditCard className="h-4 w-4" />
          {pending ? t('processing') : t('completeBooking')}
        </button>
      </div>
    </div>
  )
}
