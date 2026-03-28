'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import Image from 'next/image'
import { useState, useTransition } from 'react'
import { cancelBooking, submitReview } from '@/actions/bookingActions'
import { deleteCar } from '@/actions/carActions'
import { BookingPhotos } from '@/components/cars/BookingPhotos'
import {
  Car,
  CheckCircle,
  Clock,
  XCircle,
  PlusCircle,
  Calendar,
  CreditCard,
  MapPin,
  Trash2,
  Pencil,
  Ban,
  Star,
  User,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Wallet,
  FileText,
  Camera,
} from 'lucide-react'

interface DashboardClientProps {
  cars: Array<{
    id: string
    title: string
    status: string
    dailyPrice: string
    area: string
    images: string[]
    createdAt: string
    bookings: Array<{
      id: string
      status: string
      totalAmount: string
      startDate: string
      endDate: string
      renter: {
        fullName: string | null
        email: string
      }
    }>
  }>
  bookings: Array<{
    id: string
    status: string
    totalAmount: string
    totalDays: number
    startDate: string
    endDate: string
    car: {
      title: string
      images: string[]
      dailyPrice: string
      area: string
    }
    review?: {
      id: string
      rating: number
      comment: string | null
    } | null
  }>
}

const statusConfig: Record<
  string,
  { color: string; bg: string; border: string; icon: typeof CheckCircle; label: { ar: string; en: string } }
> = {
  APPROVED: {
    color: 'text-status-success',
    bg: 'bg-status-success/10',
    border: 'border-status-success/20',
    icon: CheckCircle,
    label: { ar: 'معتمدة', en: 'Approved' },
  },
  PENDING: {
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    border: 'border-status-warning/20',
    icon: Clock,
    label: { ar: 'قيد المراجعة', en: 'Pending' },
  },
  REJECTED: {
    color: 'text-red-400',
    bg: 'bg-red-400/10',
    border: 'border-red-400/20',
    icon: XCircle,
    label: { ar: 'مرفوضة', en: 'Rejected' },
  },
  AWAITING_PAYMENT: {
    color: 'text-text-secondary',
    bg: 'bg-dark-surface',
    border: 'border-dark-border',
    icon: CreditCard,
    label: { ar: 'بانتظار الدفع', en: 'Awaiting Payment' },
  },
  ACTIVE: {
    color: 'text-blue-400',
    bg: 'bg-blue-400/10',
    border: 'border-blue-400/20',
    icon: CheckCircle,
    label: { ar: 'نشط', en: 'Active' },
  },
  COMPLETED: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/10',
    border: 'border-emerald-400/20',
    icon: CheckCircle,
    label: { ar: 'مكتمل', en: 'Completed' },
  },
  CANCELLED: {
    color: 'text-text-muted',
    bg: 'bg-dark-surface',
    border: 'border-dark-border',
    icon: XCircle,
    label: { ar: 'ملغي', en: 'Cancelled' },
  },
}

export default function DashboardClient({
  cars,
  bookings: initialBookings,
}: DashboardClientProps) {
  const { t, lang } = useLanguage()
  const [bookings, setBookings] = useState(initialBookings)
  const [carList, setCarList] = useState(cars)
  const [isPending, startTransition] = useTransition()
  const [expandedCar, setExpandedCar] = useState<string | null>(null)
  const [reviewingBooking, setReviewingBooking] = useState<string | null>(null)
  const [reviewRating, setReviewRating] = useState(5)
  const [reviewComment, setReviewComment] = useState('')

  const totalApproved = carList.filter((c) => c.status === 'APPROVED').length
  const totalPending = carList.filter((c) => c.status === 'PENDING').length
  const totalRejected = carList.filter((c) => c.status === 'REJECTED').length
  const totalNewBookings = carList.reduce(
    (sum, car) => sum + car.bookings.filter((b) => b.status === 'APPROVED' || b.status === 'AWAITING_PAYMENT').length,
    0
  )

  // Earnings calculations
  const allBookings = carList.reduce((acc, car) => acc.concat(car.bookings), [] as any[])
  const totalEarnings = allBookings
    .filter((b) => b.status === 'COMPLETED' || b.status === 'ACTIVE')
    .reduce((sum, b) => sum + parseFloat(String(b.totalAmount) || '0'), 0)

  const currentMonth = new Date().getMonth()
  const currentYear = new Date().getFullYear()
  const thisMonthEarnings = allBookings
    .filter((b) => {
      const bookingDate = new Date(b.startDate)
      return (
        (b.status === 'COMPLETED' || b.status === 'ACTIVE') &&
        bookingDate.getMonth() === currentMonth &&
        bookingDate.getFullYear() === currentYear
      )
    })
    .reduce((sum, b) => sum + parseFloat(String(b.totalAmount) || '0'), 0)

  const pendingEarnings = allBookings
    .filter((b) => b.status === 'AWAITING_PAYMENT' || b.status === 'APPROVED')
    .reduce((sum, b) => sum + parseFloat(String(b.totalAmount) || '0'), 0)

  function StatusBadge({ status }: { status: string }) {
    const config = statusConfig[status] || statusConfig.PENDING
    const Icon = config.icon
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${config.bg} ${config.border} ${config.color}`}
      >
        <Icon className="h-3 w-3" />
        {config.label[lang]}
      </span>
    )
  }

  function handleCancelBooking(bookingId: string) {
    startTransition(async () => {
      const result = await cancelBooking(bookingId)
      if (result.success) {
        setBookings((prev) =>
          prev.map((b) =>
            b.id === bookingId ? { ...b, status: 'CANCELLED' } : b
          )
        )
      }
    })
  }

  function handleDeleteCar(carId: string) {
    if (!confirm(lang === 'ar' ? 'هل أنت متأكد من حذف هذه السيارة؟' : 'Are you sure you want to delete this car?')) return
    startTransition(async () => {
      const result = await deleteCar(carId)
      if (result.success) {
        setCarList((prev) => prev.filter((c) => c.id !== carId))
      }
    })
  }

  function handleSubmitReview(bookingId: string) {
    startTransition(async () => {
      const result = await submitReview(bookingId, reviewRating, reviewComment)
      if (result.success) {
        setBookings((prev) =>
          prev.map((b) =>
            b.id === bookingId
              ? { ...b, review: { id: 'new', rating: reviewRating, comment: reviewComment || null } }
              : b
          )
        )
        setReviewingBooking(null)
        setReviewRating(5)
        setReviewComment('')
      }
    })
  }

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString(lang === 'ar' ? 'ar-KW' : 'en-US')

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-text-primary">{t('dashboard')}</h1>
        <Link href="/list" className="btn-primary flex items-center gap-2">
          <PlusCircle className="h-4 w-4" />
          {t('listCar')}
        </Link>
      </div>

      {/* Stats */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[
          { label: t('totalCars'), value: carList.length, icon: Car },
          { label: t('approved'), value: totalApproved, icon: CheckCircle },
          { label: t('pendingReview'), value: totalPending, icon: Clock },
          { label: t('rejected'), value: totalRejected, icon: XCircle },
          { label: lang === 'ar' ? 'حجوزات جديدة' : 'New Bookings', value: totalNewBookings, icon: Calendar },
        ].map((stat, i) => (
          <div key={i} className="card flex items-center gap-4">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-dark-surface border border-dark-border-light shadow-lg">
              <stat.icon className="h-6 w-6 text-status-star" />
            </div>
            <div>
              <div className="text-2xl font-bold text-text-primary">{stat.value}</div>
              <div className="text-sm text-text-secondary">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Earnings Summary */}
      <section className="mb-10">
        <h2 className="mb-4 text-xl font-bold text-text-primary">
          {lang === 'ar' ? 'الأرباح' : 'Earnings'}
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {/* Total Earnings */}
          <div className="card flex items-center gap-4">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-dark-surface border border-dark-border-light shadow-lg">
              <TrendingUp className="h-6 w-6 text-status-star" />
            </div>
            <div>
              <div className="text-2xl font-bold text-status-star">{totalEarnings.toFixed(2)}</div>
              <div className="text-sm text-text-secondary">
                {lang === 'ar' ? 'إجمالي الأرباح' : 'Total Earnings'}
              </div>
            </div>
          </div>

          {/* This Month Earnings */}
          <div className="card flex items-center gap-4">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-dark-surface border border-dark-border-light shadow-lg">
              <Wallet className="h-6 w-6 text-status-star" />
            </div>
            <div>
              <div className="text-2xl font-bold text-status-star">{thisMonthEarnings.toFixed(2)}</div>
              <div className="text-sm text-text-secondary">
                {lang === 'ar' ? 'هذا الشهر' : 'This Month'}
              </div>
            </div>
          </div>

          {/* Pending Earnings */}
          <div className="card flex items-center gap-4">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-dark-surface border border-dark-border-light shadow-lg">
              <Clock className="h-6 w-6 text-status-star" />
            </div>
            <div>
              <div className="text-2xl font-bold text-status-star">{pendingEarnings.toFixed(2)}</div>
              <div className="text-sm text-text-secondary">
                {lang === 'ar' ? 'قيد الانتظار' : 'Pending'}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* My Cars */}
      <section className="mb-10">
        <h2 className="mb-4 text-xl font-bold text-text-primary">
          {lang === 'ar' ? 'سياراتي' : 'My Cars'}
        </h2>

        {carList.length === 0 ? (
          <div className="card flex flex-col items-center py-12 text-center">
            <Car className="mb-4 h-12 w-12 text-text-muted" />
            <p className="mb-4 text-text-secondary">
              {lang === 'ar' ? 'لم تضف أي سيارة بعد' : "You haven't listed any cars yet"}
            </p>
            <Link href="/list" className="btn-primary">{t('listCar')}</Link>
          </div>
        ) : (
          <div className="space-y-4">
            {carList.map((car) => (
              <div key={car.id} className="card overflow-hidden !p-0">
                <div className="flex flex-col sm:flex-row">
                  {/* Image */}
                  <div className="relative h-48 w-full sm:h-auto sm:w-44 flex-shrink-0">
                    {car.images?.[0] ? (
                      <Image src={car.images[0]} alt={car.title} fill className="object-cover" />
                    ) : (
                      <div className="flex h-full min-h-[120px] items-center justify-center bg-dark-surface">
                        <Car className="h-8 w-8 text-text-muted" />
                      </div>
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex-1 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-bold text-text-primary">{car.title}</h3>
                        <div className="mt-1 flex items-center gap-3 text-sm text-text-secondary">
                          <span className="flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5" />
                            {car.area}
                          </span>
                          <span className="font-medium text-status-star">
                            {String(car.dailyPrice)} {t('perDay')}
                          </span>
                        </div>
                      </div>
                      <StatusBadge status={car.status} />
                    </div>

                    {/* Actions */}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Link
                        href={`/edit/${car.id}`}
                        className="inline-flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary hover:bg-dark-surface transition-colors"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        {lang === 'ar' ? 'تعديل' : 'Edit'}
                      </Link>
                      <button
                        onClick={() => handleDeleteCar(car.id)}
                        disabled={isPending}
                        className="inline-flex items-center gap-1 rounded-lg bg-red-400/10 border border-red-400/20 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-400/20 transition-colors disabled:opacity-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {lang === 'ar' ? 'حذف' : 'Delete'}
                      </button>

                      {/* Toggle bookings */}
                      {car.bookings.length > 0 && (
                        <button
                          onClick={() => setExpandedCar(expandedCar === car.id ? null : car.id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary hover:bg-dark-surface transition-colors"
                        >
                          <Calendar className="h-3.5 w-3.5" />
                          {car.bookings.length} {lang === 'ar' ? 'حجز' : 'bookings'}
                          {expandedCar === car.id ? (
                            <ChevronUp className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronDown className="h-3.5 w-3.5" />
                          )}
                        </button>
                      )}
                    </div>

                    {/* Expanded Bookings */}
                    {expandedCar === car.id && car.bookings.length > 0 && (
                      <div className="mt-3 space-y-2 border-t border-dark-border pt-3">
                        <p className="text-xs font-medium text-text-secondary mb-2">
                          {lang === 'ar' ? 'الحجوزات على هذه السيارة:' : 'Bookings on this car:'}
                        </p>
                        {car.bookings.map((booking) => (
                          <div
                            key={booking.id}
                            className="flex flex-col gap-2 rounded-xl bg-dark-surface p-3 text-sm"
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="flex items-center gap-1 font-medium text-text-primary">
                                  <User className="h-3.5 w-3.5 text-text-secondary" />
                                  {booking.renter.fullName || booking.renter.email}
                                </p>
                                <p className="mt-0.5 text-xs text-text-secondary">
                                  {formatDate(booking.startDate)} → {formatDate(booking.endDate)}
                                  <span className="ms-2 text-status-star">{booking.totalAmount} {lang === 'ar' ? 'د.ك' : 'KWD'}</span>
                                </p>
                              </div>
                              <StatusBadge status={booking.status} />
                            </div>
                            {booking.status === 'ACTIVE' && (
                              <Link
                                href={`/inspection/${booking.id}`}
                                className="inline-flex items-center justify-center gap-1 rounded-lg bg-status-star/10 border border-status-star/20 px-2 py-1.5 text-xs font-medium text-status-star hover:bg-status-star/20 transition-colors"
                              >
                                <Camera className="h-3.5 w-3.5" />
                                {lang === 'ar' ? 'توثيق الإرجاع' : 'Document Return'}
                              </Link>
                            )}
                            {/* Owner delivery photos */}
                            {['APPROVED', 'ACTIVE'].includes(booking.status) && (
                              <BookingPhotos bookingId={booking.id} role="OWNER" phase="DELIVERY" />
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* My Bookings */}
      <section>
        <h2 className="mb-4 text-xl font-bold text-text-primary">
          {t('myBookings')}
        </h2>

        {bookings.length === 0 ? (
          <div className="card flex flex-col items-center py-12 text-center">
            <Calendar className="mb-4 h-12 w-12 text-text-muted" />
            <p className="mb-4 text-text-secondary">
              {lang === 'ar' ? 'لا توجد حجوزات حتى الآن' : 'No bookings yet'}
            </p>
            <Link href="/browse" className="btn-primary">{t('browseNow')}</Link>
          </div>
        ) : (
          <div className="space-y-4">
            {bookings.map((booking) => (
              <div key={booking.id} className="card">
                <div className="flex gap-4">
                  <div className="relative h-20 w-28 flex-shrink-0 overflow-hidden rounded-xl bg-dark-surface">
                    {booking.car.images?.[0] ? (
                      <Image src={booking.car.images[0]} alt={booking.car.title} fill className="object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        <Car className="h-6 w-6 text-text-muted" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="mb-1 flex items-start justify-between">
                      <h3 className="font-bold text-text-primary">{booking.car.title}</h3>
                      <StatusBadge status={booking.status} />
                    </div>
                    <div className="flex flex-wrap gap-3 text-sm text-text-secondary">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        {formatDate(booking.startDate)} → {formatDate(booking.endDate)}
                      </span>
                      <span className="font-medium text-status-star">
                        {String(booking.totalAmount)} {lang === 'ar' ? 'د.ك' : 'KWD'}
                      </span>
                    </div>

                    {/* Actions row */}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {/* View Contract button */}
                      {['APPROVED', 'ACTIVE', 'COMPLETED'].includes(booking.status) && (
                        <Link
                          href={`/contract/${booking.id}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-blue-400/10 border border-blue-400/20 px-3 py-1.5 text-xs font-medium text-blue-400 hover:bg-blue-400/20 transition-colors"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          {lang === 'ar' ? 'عرض العقد' : 'View Contract'}
                        </Link>
                      )}

                      {/* Document Inspection button */}
                      {booking.status === 'ACTIVE' && (
                        <Link
                          href={`/inspection/${booking.id}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-status-star/10 border border-status-star/20 px-3 py-1.5 text-xs font-medium text-status-star hover:bg-status-star/20 transition-colors"
                        >
                          <Camera className="h-3.5 w-3.5" />
                          {lang === 'ar' ? 'توثيق الاستلام' : 'Document Pickup'}
                        </Link>
                      )}

                      {/* Cancel button */}
                      {!['COMPLETED', 'CANCELLED', 'ACTIVE'].includes(booking.status) && (
                        <button
                          onClick={() => handleCancelBooking(booking.id)}
                          disabled={isPending}
                          className="inline-flex items-center gap-1 rounded-lg bg-red-400/10 border border-red-400/20 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-400/20 transition-colors disabled:opacity-50"
                        >
                          <Ban className="h-3.5 w-3.5" />
                          {lang === 'ar' ? 'إلغاء الحجز' : 'Cancel'}
                        </button>
                      )}

                      {/* Review button / display */}
                      {booking.status === 'COMPLETED' && !booking.review && (
                        <button
                          onClick={() => setReviewingBooking(reviewingBooking === booking.id ? null : booking.id)}
                          className="inline-flex items-center gap-1 rounded-lg bg-status-star/10 border border-status-star/20 px-3 py-1.5 text-xs font-medium text-status-star hover:bg-status-star/20 transition-colors"
                        >
                          <Star className="h-3.5 w-3.5" />
                          {lang === 'ar' ? 'أضف تقييم' : 'Add Review'}
                        </button>
                      )}

                      {booking.review && (
                        <div className="inline-flex items-center gap-1 text-xs text-status-star">
                          {Array.from({ length: booking.review.rating }).map((_, i) => (
                            <Star key={i} className="h-3.5 w-3.5 fill-status-star" />
                          ))}
                          {booking.review.comment && (
                            <span className="ms-1 text-text-secondary">"{booking.review.comment}"</span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Renter return photos */}
                    {['ACTIVE', 'COMPLETED'].includes(booking.status) && (
                      <div className="mt-2">
                        <BookingPhotos bookingId={booking.id} role="RENTER" phase="RETURN" />
                      </div>
                    )}

                    {/* Review form */}
                    {reviewingBooking === booking.id && (
                      <div className="mt-3 rounded-xl bg-dark-surface p-4 border border-dark-border">
                        <div className="mb-3">
                          <label className="mb-1 block text-xs text-text-secondary">
                            {lang === 'ar' ? 'التقييم' : 'Rating'}
                          </label>
                          <div className="flex gap-1">
                            {[1, 2, 3, 4, 5].map((star) => (
                              <button
                                key={star}
                                onClick={() => setReviewRating(star)}
                                className="transition-transform hover:scale-110"
                              >
                                <Star
                                  className={`h-6 w-6 ${
                                    star <= reviewRating
                                      ? 'fill-status-star text-status-star'
                                      : 'text-dark-border'
                                  }`}
                                />
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="mb-3">
                          <label className="mb-1 block text-xs text-text-secondary">
                            {lang === 'ar' ? 'تعليق (اختياري)' : 'Comment (optional)'}
                          </label>
                          <textarea
                            value={reviewComment}
                            onChange={(e) => setReviewComment(e.target.value)}
                            rows={2}
                            placeholder={lang === 'ar' ? 'كيف كانت تجربتك؟' : 'How was your experience?'}
                            className="w-full rounded-lg border border-dark-border bg-dark-card p-2 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-dark-border-light"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSubmitReview(booking.id)}
                            disabled={isPending}
                            className="rounded-lg bg-status-star px-4 py-1.5 text-xs font-medium text-dark-bg hover:bg-status-star/90 transition-colors disabled:opacity-50"
                          >
                            {lang === 'ar' ? 'إرسال التقييم' : 'Submit Review'}
                          </button>
                          <button
                            onClick={() => setReviewingBooking(null)}
                            className="rounded-lg border border-dark-border px-4 py-1.5 text-xs text-text-secondary hover:bg-dark-card transition-colors"
                          >
                            {lang === 'ar' ? 'إلغاء' : 'Cancel'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
