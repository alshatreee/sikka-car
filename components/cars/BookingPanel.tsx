'use client'

import { useState, useTransition, useMemo, useEffect } from 'react'
import { createBooking, getBookedDates } from '@/actions/bookingActions'
import { initiatePayment } from '@/actions/paymentActions'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { uploadToCloudinary } from '@/utils/uploadImage'
import { Calendar, Clock, FileText, CreditCard, AlertTriangle, Shield, Upload, Camera, Loader2, Check, LogIn } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'

interface BookingPanelProps {
  carId: string
  dailyPrice: number
  customerName?: string
  customerEmail?: string
  isGuest?: boolean
}

export function BookingPanel({
  carId,
  dailyPrice,
  customerName,
  customerEmail,
  isGuest = false,
}: BookingPanelProps) {
  const { t, lang } = useLanguage()
  const [pending, startTransition] = useTransition()
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [pickupTime, setPickupTime] = useState('')
  const [dropoffTime, setDropoffTime] = useState('')
  const [civilId, setCivilId] = useState('')
  const [licenseNumber, setLicenseNumber] = useState('')
  const [civilIdImageFront, setCivilIdImageFront] = useState('')
  const [civilIdImageBack, setCivilIdImageBack] = useState('')
  const [licenseImageFront, setLicenseImageFront] = useState('')
  const [licenseImageBack, setLicenseImageBack] = useState('')
  const [uploadingCivilFront, setUploadingCivilFront] = useState(false)
  const [uploadingCivilBack, setUploadingCivilBack] = useState(false)
  const [uploadingLicenseFront, setUploadingLicenseFront] = useState(false)
  const [uploadingLicenseBack, setUploadingLicenseBack] = useState(false)
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

    if (isGuest) {
      window.location.href = '/sign-in'
      return
    }

    if (!startDate || !endDate) {
      setError(lang === 'ar' ? 'ÙØ±Ø¬Ù ØªØ­Ø¯ÙØ¯ ØªÙØ§Ø±ÙØ® Ø§ÙØ­Ø¬Ø²' : 'Please select booking dates')
      return
    }

    if (totalDays <= 0) {
      setError(lang === 'ar' ? 'ØªØ§Ø±ÙØ® Ø§ÙÙÙØ§ÙØ© ÙØ¬Ø¨ Ø£Ù ÙÙÙÙ Ø¨Ø¹Ø¯ ØªØ§Ø±ÙØ® Ø§ÙØ¨Ø¯Ø§ÙØ©' : 'End date must be after start date')
      return
    }

    if (!civilId && !civilIdImageFront) {
      setError(lang === 'ar' ? 'ÙØ±Ø¬Ù Ø¥Ø¯Ø®Ø§Ù Ø§ÙØ±ÙÙ Ø§ÙÙØ¯ÙÙ Ø£Ù Ø±ÙØ¹ ØµÙØ±Ø© Ø§ÙØ¨Ø·Ø§ÙØ© Ø§ÙÙØ¯ÙÙØ©' : 'Please enter Civil ID or upload Civil ID image')
      return
    }
    if (civilId && !/^\d{12}$/.test(civilId)) {
      setError(lang === 'ar' ? 'Ø§ÙØ±ÙÙ Ø§ÙÙØ¯ÙÙ ÙØ¬Ø¨ Ø£Ù ÙÙÙÙ 12 Ø±ÙÙ' : 'Civil ID must be exactly 12 digits')
      return
    }
    if (!licenseNumber && !licenseImageFront) {
      setError(lang === 'ar' ? 'ÙØ±Ø¬Ù Ø¥Ø¯Ø®Ø§Ù Ø±ÙÙ Ø§ÙØ±Ø®ØµØ© Ø£Ù Ø±ÙØ¹ ØµÙØ±Ø© Ø§ÙØ±Ø®ØµØ©' : 'Please enter License Number or upload License image')
      return
    }

    if (!contractAccepted) {
      setError(lang === 'ar' ? 'ÙØ¬Ø¨ ÙØ¨ÙÙ Ø´Ø±ÙØ· Ø¹ÙØ¯ Ø§ÙØªØ£Ø¬ÙØ±' : 'You must accept the rental agreement terms')
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
        civilId: civilId || undefined,
        licenseNumber: licenseNumber || undefined,
        civilIdImageFront: civilIdImageFront || undefined,
        civilIdImageBack: civilIdImageBack || undefined,
        licenseImageFront: licenseImageFront || undefined,
        licenseImageBack: licenseImageBack || undefined,
        notes,
      })

      if (!bookingResult.success || !bookingResult.bookingId) {
        setError(
          bookingResult.error || 'Ø­Ø¯Ø« Ø®Ø·Ø£ Ø£Ø«ÙØ§Ø¡ Ø¥ÙØ´Ø§Ø¡ Ø§ÙØ­Ø¬Ø²'
        )
        return
      }

      const paymentResult = await initiatePayment(
        bookingResult.totalAmount,
        bookingResult.bookingId,
        customerName || '',
        customerEmail || ''
      )

      if (paymentResult.success && paymentResult.checkoutUrl) {
        window.location.href = paymentResult.checkoutUrl
      } else {
        setError(paymentResult.error || 'ÙØ´Ù Ø¥ÙØ´Ø§Ø¡ Ø±Ø§Ø¨Ø· Ø§ÙØ¯ÙØ¹')
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

        {/* Identity Verification - Civil ID */}
        <div className="rounded-xl border border-dark-border bg-dark-surface/50 p-4 space-y-3">
          <label className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
            <Shield className="h-4 w-4 text-status-star" />
            {lang === 'ar' ? 'Ø§ÙØ¨Ø·Ø§ÙØ© Ø§ÙÙØ¯ÙÙØ©' : 'Civil ID'}
          </label>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              {lang === 'ar' ? 'Ø§ÙØ±ÙÙ Ø§ÙÙØ¯ÙÙ' : 'Civil ID Number'}
            </label>
            <input
              type="text"
              value={civilId}
              onChange={(e) => setCivilId(e.target.value.replace(/\D/g, '').slice(0, 12))}
              placeholder="123456789012"
              maxLength={12}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                {lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ£ÙØ§ÙÙ' : 'Front Side'}
              </label>
              {civilIdImageFront ? (
                <div className="relative h-24 w-full overflow-hidden rounded-xl border border-green-500/30">
                  <Image src={civilIdImageFront} alt="Civil ID Front" fill className="object-cover" />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                    <Check className="h-6 w-6 text-green-400" />
                  </div>
                  <button type="button" onClick={() => setCivilIdImageFront('')} className="absolute top-1 end-1 rounded-full bg-dark-bg/80 p-1 text-text-muted hover:text-text-primary">â</button>
                </div>
              ) : (
                <label className="flex h-24 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                  {uploadingCivilFront ? <Loader2 className="h-6 w-6 animate-spin text-text-muted" /> : (
                    <><Camera className="mb-1 h-5 w-5 text-text-muted" /><span className="text-[10px] text-text-muted">{lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ£ÙØ§ÙÙ' : 'Front'}</span></>
                  )}
                  <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                    const file = e.target.files?.[0]; if (!file) return
                    setUploadingCivilFront(true)
                    const url = await uploadToCloudinary(file, 'sikka_id_docs')
                    if (url) setCivilIdImageFront(url)
                    setUploadingCivilFront(false)
                  }} />
                </label>
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                {lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ®ÙÙÙ' : 'Back Side'}
              </label>
              {civilIdImageBack ? (
                <div className="relative h-24 w-full overflow-hidden rounded-xl border border-green-500/30">
                  <Image src={civilIdImageBack} alt="Civil ID Back" fill className="object-cover" />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                    <Check className="h-6 w-6 text-green-400" />
                  </div>
                  <button type="button" onClick={() => setCivilIdImageBack('')} className="absolute top-1 end-1 rounded-full bg-dark-bg/80 p-1 text-text-muted hover:text-text-primary">â</button>
                </div>
              ) : (
                <label className="flex h-24 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                  {uploadingCivilBack ? <Loader2 className="h-6 w-6 animate-spin text-text-muted" /> : (
                    <><Camera className="mb-1 h-5 w-5 text-text-muted" /><span className="text-[10px] text-text-muted">{lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ®ÙÙÙ' : 'Back'}</span></>
                  )}
                  <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                    const file = e.target.files?.[0]; if (!file) return
                    setUploadingCivilBack(true)
                    const url = await uploadToCloudinary(file, 'sikka_id_docs')
                    if (url) setCivilIdImageBack(url)
                    setUploadingCivilBack(false)
                  }} />
                </label>
              )}
            </div>
          </div>
        </div>

        {/* Identity Verification - License */}
        <div className="rounded-xl border border-dark-border bg-dark-surface/50 p-4 space-y-3">
          <label className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
            <CreditCard className="h-4 w-4 text-status-star" />
            {lang === 'ar' ? 'Ø±Ø®ØµØ© Ø§ÙÙÙØ§Ø¯Ø©' : 'Driving License'}
          </label>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              {lang === 'ar' ? 'Ø±ÙÙ Ø§ÙØ±Ø®ØµØ©' : 'License Number'}
            </label>
            <input
              type="text"
              value={licenseNumber}
              onChange={(e) => setLicenseNumber(e.target.value)}
              placeholder={lang === 'ar' ? 'Ø±ÙÙ Ø§ÙØ±Ø®ØµØ©' : 'License number'}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                {lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ£ÙØ§ÙÙ' : 'Front Side'}
              </label>
              {licenseImageFront ? (
                <div className="relative h-24 w-full overflow-hidden rounded-xl border border-green-500/30">
                  <Image src={licenseImageFront} alt="License Front" fill className="object-cover" />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                    <Check className="h-6 w-6 text-green-400" />
                  </div>
                  <button type="button" onClick={() => setLicenseImageFront('')} className="absolute top-1 end-1 rounded-full bg-dark-bg/80 p-1 text-text-muted hover:text-text-primary">â</button>
                </div>
              ) : (
                <label className="flex h-24 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                  {uploadingLicenseFront ? <Loader2 className="h-6 w-6 animate-spin text-text-muted" /> : (
                    <><Camera className="mb-1 h-5 w-5 text-text-muted" /><span className="text-[10px] text-text-muted">{lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ£ÙØ§ÙÙ' : 'Front'}</span></>
                  )}
                  <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                    const file = e.target.files?.[0]; if (!file) return
                    setUploadingLicenseFront(true)
                    const url = await uploadToCloudinary(file, 'sikka_id_docs')
                    if (url) setLicenseImageFront(url)
                    setUploadingLicenseFront(false)
                  }} />
                </label>
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                {lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ®ÙÙÙ' : 'Back Side'}
              </label>
              {licenseImageBack ? (
                <div className="relative h-24 w-full overflow-hidden rounded-xl border border-green-500/30">
                  <Image src={licenseImageBack} alt="License Back" fill className="object-cover" />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                    <Check className="h-6 w-6 text-green-400" />
                  </div>
                  <button type="button" onClick={() => setLicenseImageBack('')} className="absolute top-1 end-1 rounded-full bg-dark-bg/80 p-1 text-text-muted hover:text-text-primary">â</button>
                </div>
              ) : (
                <label className="flex h-24 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                  {uploadingLicenseBack ? <Loader2 className="h-6 w-6 animate-spin text-text-muted" /> : (
                    <><Camera className="mb-1 h-5 w-5 text-text-muted" /><span className="text-[10px] text-text-muted">{lang === 'ar' ? 'Ø§ÙÙØ¬Ù Ø§ÙØ®ÙÙÙ' : 'Back'}</span></>
                  )}
                  <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                    const file = e.target.files?.[0]; if (!file) return
                    setUploadingLicenseBack(true)
                    const url = await uploadToCloudinary(file, 'sikka_id_docs')
                    if (url) setLicenseImageBack(url)
                    setUploadingLicenseBack(false)
                  }} />
                </label>
              )}
            </div>
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
            {lang === 'ar' ? 'Ø§ÙØ³ÙØ§Ø±Ø© ÙØ­Ø¬ÙØ²Ø© ÙÙ ÙØ°Ù Ø§ÙÙØªØ±Ø©Ø Ø§Ø®ØªØ± ØªÙØ§Ø±ÙØ® Ø£Ø®Ø±Ù' : 'Car is booked during these dates, choose different dates'}
          </div>
        )}

        {/* Booked Dates Info */}
        {bookedRanges.length > 0 && (
          <div className="rounded-xl bg-dark-surface p-3 border border-dark-border">
            <p className="mb-2 text-xs font-medium text-text-secondary">
              {lang === 'ar' ? 'Ø§ÙØªÙØ§Ø±ÙØ® Ø§ÙÙØ­Ø¬ÙØ²Ø©:' : 'Booked dates:'}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {bookedRanges.map((range, i) => (
                <span key={i} className="rounded-lg bg-red-500/10 px-2 py-1 text-xs text-red-400 border border-red-500/20">
                  {range.start} â {range.end}
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
                  {lang === 'ar' ? 'Ø£ÙØ§ÙÙ Ø¹ÙÙ Ø´Ø±ÙØ· ÙØ£Ø­ÙØ§Ù Ø¹ÙØ¯ Ø§ÙØªØ£Ø¬ÙØ±' : 'I agree to the rental agreement terms'}
                </p>
                <a
                  href="/terms"
                  className="text-xs text-status-star hover:underline"
                >
                  {lang === 'ar' ? 'Ø¹Ø±Ø¶ Ø§ÙØ´Ø±ÙØ·' : 'View terms'}
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
                {dailyPrice} {t('perDay')} Ã {totalDays}{' '}
                {totalDays === 1 ? 'ÙÙÙ' : 'Ø£ÙØ§Ù'}
              </span>
              <span className="text-lg font-bold text-status-star">
                {totalAmount.toFixed(2)} Ø¯.Ù
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
              <>Ø£ÙØ§ÙÙ Ø¹ÙÙ <a href="/terms" className="text-status-star underline">Ø´Ø±ÙØ· Ø§ÙØ§Ø³ØªØ®Ø¯Ø§Ù</a> Ù<a href="/privacy" className="text-status-star underline">Ø³ÙØ§Ø³Ø© Ø§ÙØ®ØµÙØµÙØ©</a></>
            ) : (
              <>I agree to the <a href="/terms" className="text-status-star underline">Terms of Service</a> and <a href="/privacy" className="text-status-star underline">Privacy Policy</a></>
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
              {lang === 'ar' ? 'ØªØ£ÙÙØ¯ Ø§ÙØ­Ø¬Ø²' : 'Confirm Booking'}
            </p>
            <div className="mb-3 space-y-1 text-xs text-text-secondary">
              <p>{lang === 'ar' ? 'ÙÙ' : 'From'}: {startDate} â {endDate}</p>
              <p>{lang === 'ar' ? 'Ø§ÙÙØ¯Ø©' : 'Duration'}: {totalDays} {lang === 'ar' ? (totalDays === 1 ? 'ÙÙÙ' : 'Ø£ÙØ§Ù') : (totalDays === 1 ? 'day' : 'days')}</p>
              <p className="text-base font-bold text-status-star">{totalAmount.toFixed(2)} {lang === 'ar' ? 'Ø¯.Ù' : 'KWD'}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={confirmBooking}
                disabled={pending}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-solid py-2.5 text-sm font-medium text-text-primary transition-all hover:bg-brand-solid-hover disabled:opacity-50"
              >
                <CreditCard className="h-4 w-4" />
                {pending ? t('processing') : (lang === 'ar' ? 'ØªØ£ÙÙØ¯ ÙØ§ÙØ¯ÙØ¹' : 'Confirm & Pay')}
              </button>
              <button
                onClick={() => setShowConfirm(false)}
                disabled={pending}
                className="rounded-xl border border-dark-border bg-dark-surface px-4 py-2.5 text-sm text-text-secondary transition-all hover:bg-dark-border disabled:opacity-50"
              >
                {lang === 'ar' ? 'Ø¥ÙØºØ§Ø¡' : 'Cancel'}
              </button>
            </div>
          </div>
        )}

        {!showConfirm && (
          isGuest ? (
            <Link
              href="/sign-in"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-status-star py-3.5 font-medium text-dark-bg shadow-lg transition-all hover:bg-status-star/90"
            >
              <LogIn className="h-4 w-4" />
              {lang === 'ar' ? 'Ø³Ø¬ÙÙ Ø¯Ø®ÙÙÙ ÙØ¥ØªÙØ§Ù Ø§ÙØ­Ø¬Ø²' : 'Sign in to complete booking'}
            </Link>
          ) : (
            <button
              onClick={handleBooking}
              disabled={pending || totalDays <= 0 || dateConflict || !agreedToTerms}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CreditCard className="h-4 w-4" />
              {t('completeBooking')}
            </button>
          )
        )}
      </div>
    </div>
  )
}
