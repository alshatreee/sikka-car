'use client'

import { useState, useTransition, useMemo, useEffect } from 'react'
import { createBooking, getBookedDates } from '@/actions/bookingActions'
import { initiatePayment } from '@/actions/paymentActions'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Calendar, Clock, FileText, CreditCard, AlertTriangle, Shield } from 'lucide-react'

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
  const { t, lang } = useLanguage()
  const [pending, startTransition] = useTransition()
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [pickupTime, setPickupTime] = useState('')
  const [dropoffTime, setDropoffTime] = useState('')
  const [civilId, setCivilId] = useState('')
  const [licenseNumber, setLicenseNumber] = useState('')
  const [notes, setNotes] = useState('')
  const [contractAccepted, setContractAccepted] = useState(false)
  const [error, setError] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [bookedRanges, setBookedRanges] = useState<{ start: string; end: string }[]>([])
  const [dateConflict, setDateConflict] = useState(false)

  useEffect(() => {
    getBookedDates(carId).then(setBookedRanges)
  }, [carId])

  // Check if selected dates overlap with existing bookings
  useEffect(() => {
    if (!startDate || !endDate || bookedRanges.length === 0) {
      setDateConflict(false)
      return
    }
    const hasConflict = bookedRanges.some(
      (range) => startDate < range.end && endDate > range.start
    )
    setDateConflict(hasConflict)
  }, [startDate, endDate, bookedRanges])

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
      setError(lang === 'ar' ? 'يرجى تحديد تواريخ الحجز' : 'Please select booking dates')
      return
    }

    if (totalDays <= 0) {
      setError(lang === 'ar' ? 'تاريخ النهاية يجب أن يكون بعد تاريخ البداية' : 'End date must be after start date')
      return
    }

    if (!civilId) {
      setError(lang === 'ar' ? 'يرجى إدخال الرقم المدني' : 'Please enter Civil ID')
      return
    }

    if (!/^\d{12}$/.test(civilId)) {
      setError(lang === 'ar' ? 'الرقم المدني يجب أن يكون 12 رقم' : 'Civil ID must be exactly 12 digits')
      return
    }

    if (!licenseNumber) {
      setError(lang === 'ar' ? 'يرجى إدخال رقم الرخصة' : 'Please enter License Number')
      return
    }

    if (!contractAccepted) {
      setError(lang === 'ar' ? 'يجب قبول شروط عقد التأجير' : 'You must accept the rental agreement terms')
      return
    }

    setShowConfirm(true)
  }

  function confirmBooking() {
    setShowConfirm(false)
    startTransition(async () => {
      const bookingResult = await createBooking({
        carId,
        startDate,
        endDate,
        pickupTime,
        dropoffTime,
        civilId,
        licenseNumber,
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

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
              <Shield className="h-3.5 w-3.5 text-text-secondary" />
              {lang === 'ar' ? 'الرقم المدني' : 'Civil ID'}
            </label>
            <input
              type="text"
              value={civilId}
              onChange={(e) => setCivilId(e.target.value.replace(/\D/g, '').slice(0, 12))}
              placeholder={lang === 'ar' ? '123456789012' : '123456789012'}
              maxLength={12}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
          <div>
            <label className="mb-1 flex items-center gap-1 text-sm font-medium text-text-primary">
              <Shield className="h-3.5 w-3.5 text-text-secondary" />
              {lang === 'ar' ? 'رقم الرخصة' : 'License Number'}
            </label>
            <input
              type="text"
              value={licenseNumber}
              onChange={(e) => setLicenseNumber(e.target.value)}
              placeholder={lang === 'ar' ? 'أدخل رقم الرخصة' : 'Enter license number'}
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

        {/* Date Conflict Warning */}
        {dateConflict && (
          <div className="flex items-center gap-2 rounded-xl bg-red-500/10 p-3 text-sm text-red-400 border border-red-500/20">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {lang === 'ar' ? 'السيارة محجوزة في هذه الفترة، اختر تواريخ أخرى' : 'Car is booked during these dates, choose different dates'}
          </div>
        )}

        {/* Booked Dates Info */}
        {bookedRanges.length > 0 && (
          <div className="rounded-xl bg-dark-surface p-3 border border-dark-border">
            <p className="mb-2 text-xs font-medium text-text-secondary">
              {lang === 'ar' ? 'التواريخ المحجوزة:' : 'Booked dates:'}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {bookedRanges.map((range, i) => (
                <span key={i} className="rounded-lg bg-red-500/10 px-2 py-1 text-xs text-red-400 border border-red-500/20">
                  {range.start} → {range.end}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Contract Agreement Checkbox */}
        {totalDays > 0 && !dateConflict && (
          <div className="rounded-xl border border-dark-border bg-dark-surface/50 p-3">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={contractAccepted}
                onChange={(e) => setContractAccepted(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-dark-border bg-dark-surface text-status-star outline-none accent-status-star"
              />
              <div className="flex-1">
                <p className="text-sm text-text-primary">
                  {lang === 'ar' ? 'أوافق على شروط وأحكام عقد التأجير' : 'I agree to the rental agreement terms'}
                </p>
                <a
                  href="javascript:void(0)"
                  onClick={(e) => {
                    e.preventDefault()
                    // This will be used if we want to show the full contract in a modal
                    // For now, users can view it after booking
                  }}
                  className="text-xs text-status-star hover:underline"
                >
                  {lang === 'ar' ? 'عرض الشروط' : 'View terms'}
                </a>
              </div>
            </label>
          </div>
        )}

        {/* Price Summary */}
        {totalDays > 0 && !dateConflict && (
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

        {/* Terms Agreement */}
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agreedToTerms}
            onChange={(e) => setAgreedToTerms(e.target.checked)}
            className="mt-1 h-4 w-4 shrink-0 rounded border-dark-border accent-status-star"
          />
          <span className="text-xs text-text-secondary">
            {lang === 'ar' ? (
              <>أوافق على <a href="/terms" target="_blank" className="text-status-star underline">شروط الاستخدام</a> و<a href="/privacy" target="_blank" className="text-status-star underline">سياسة الخصوصية</a></>
            ) : (
              <>I agree to the <a href="/terms" target="_blank" className="text-status-star underline">Terms of Service</a> and <a href="/privacy" target="_blank" className="text-status-star underline">Privacy Policy</a></>
            )}
          </span>
        </label>

        {error && (
          <div className="rounded-xl bg-status-warning/10 p-3 text-sm text-status-warning border border-status-warning/20">
            {error}
          </div>
        )}

        {/* Confirmation Dialog */}
        {showConfirm && (
          <div className="rounded-xl border border-status-star/30 bg-status-star/5 p-4">
            <p className="mb-3 text-sm font-medium text-text-primary">
              {lang === 'ar' ? 'تأكيد الحجز' : 'Confirm Booking'}
            </p>
            <div className="mb-3 space-y-1 text-xs text-text-secondary">
              <p>{lang === 'ar' ? 'من' : 'From'}: {startDate} → {endDate}</p>
              <p>{lang === 'ar' ? 'المدة' : 'Duration'}: {totalDays} {lang === 'ar' ? (totalDays === 1 ? 'يوم' : 'أيام') : (totalDays === 1 ? 'day' : 'days')}</p>
              <p className="text-base font-bold text-status-star">{totalAmount.toFixed(2)} {lang === 'ar' ? 'د.ك' : 'KWD'}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={confirmBooking}
                disabled={pending}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-solid py-2.5 text-sm font-medium text-text-primary transition-all hover:bg-brand-solid-hover disabled:opacity-50"
              >
                <CreditCard className="h-4 w-4" />
                {pending ? t('processing') : (lang === 'ar' ? 'تأكيد والدفع' : 'Confirm & Pay')}
              </button>
              <button
                onClick={() => setShowConfirm(false)}
                disabled={pending}
                className="rounded-xl border border-dark-border bg-dark-surface px-4 py-2.5 text-sm text-text-secondary transition-all hover:bg-dark-border disabled:opacity-50"
              >
                {lang === 'ar' ? 'إلغاء' : 'Cancel'}
              </button>
            </div>
          </div>
        )}

        {!showConfirm && (
          <button
            onClick={handleBooking}
            disabled={pending || totalDays <= 0 || dateConflict || !agreedToTerms}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CreditCard className="h-4 w-4" />
            {t('completeBooking')}
          </button>
        )}
      </div>
    </div>
  )
}
