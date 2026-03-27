'use client'

import Image from 'next/image'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { updateBookingStatus } from '@/actions/adminActions'
import { useState, useTransition } from 'react'
import {
  CalendarCheck,
  Car,
  CheckCircle2,
  XCircle,
  Clock,
  CreditCard,
  Play,
  Ban,
} from 'lucide-react'

interface AdminBooking {
  id: string
  startDate: string
  endDate: string
  totalDays: number
  totalAmount: string
  status: string
  paymentReference?: string | null
  createdAt: string
  car: {
    title: string
    images: string[]
    area: string
    dailyPrice: string
  }
  renter: {
    fullName?: string | null
    email?: string | null
    phone?: string | null
  }
}

export default function AdminBookingsClient({
  bookings: initialBookings,
}: {
  bookings: AdminBooking[]
}) {
  const { t, lang } = useLanguage()
  const [bookings, setBookings] = useState(initialBookings)
  const [isPending, startTransition] = useTransition()
  const [statusFilter, setStatusFilter] = useState('')

  const filteredBookings = statusFilter
    ? bookings.filter((b) => b.status === statusFilter)
    : bookings

  const handleStatusChange = (
    bookingId: string,
    newStatus: 'APPROVED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | 'REJECTED'
  ) => {
    startTransition(async () => {
      await updateBookingStatus(bookingId, newStatus)
      setBookings((prev) =>
        prev.map((b) =>
          b.id === bookingId ? { ...b, status: newStatus } : b
        )
      )
    })
  }

  const statusBadge = (status: string) => {
    const configs: Record<string, { icon: typeof Clock; color: string; bg: string; border: string; label: string }> = {
      PENDING: { icon: Clock, color: 'text-text-secondary', bg: 'bg-dark-surface', border: 'border-dark-border', label: lang === 'ar' ? 'معلق' : 'Pending' },
      AWAITING_PAYMENT: { icon: CreditCard, color: 'text-status-warning', bg: 'bg-status-warning/10', border: 'border-status-warning/20', label: lang === 'ar' ? 'بانتظار الدفع' : 'Awaiting Payment' },
      APPROVED: { icon: CheckCircle2, color: 'text-status-success', bg: 'bg-status-success/10', border: 'border-status-success/20', label: t('approved') },
      ACTIVE: { icon: Play, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/20', label: lang === 'ar' ? 'نشط' : 'Active' },
      COMPLETED: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20', label: lang === 'ar' ? 'مكتمل' : 'Completed' },
      CANCELLED: { icon: Ban, color: 'text-text-muted', bg: 'bg-dark-surface', border: 'border-dark-border', label: lang === 'ar' ? 'ملغي' : 'Cancelled' },
      REJECTED: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-400/10', border: 'border-red-400/20', label: t('rejected') },
    }
    const config = configs[status] || configs.PENDING
    const Icon = config.icon
    return (
      <span className={`inline-flex items-center gap-1 rounded-full ${config.bg} border ${config.border} px-2.5 py-1 text-xs font-medium ${config.color}`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </span>
    )
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(lang === 'ar' ? 'ar-KW' : 'en-KW')
  }

  const filters = [
    { value: '', label: lang === 'ar' ? 'الكل' : 'All' },
    { value: 'AWAITING_PAYMENT', label: lang === 'ar' ? 'بانتظار الدفع' : 'Awaiting Payment' },
    { value: 'APPROVED', label: t('approved') },
    { value: 'ACTIVE', label: lang === 'ar' ? 'نشط' : 'Active' },
    { value: 'COMPLETED', label: lang === 'ar' ? 'مكتمل' : 'Completed' },
    { value: 'CANCELLED', label: lang === 'ar' ? 'ملغي' : 'Cancelled' },
  ]

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-text-primary">
        {t('adminBookings')}
      </h1>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
              statusFilter === f.value
                ? 'bg-status-star text-dark-bg'
                : 'border border-dark-border bg-dark-card text-text-secondary hover:bg-dark-surface'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <p className="mb-4 text-sm text-text-secondary">
        {filteredBookings.length} {lang === 'ar' ? 'حجز' : 'bookings'}
      </p>

      {/* Bookings List */}
      <div className="space-y-4">
        {filteredBookings.map((booking) => (
          <div
            key={booking.id}
            className="overflow-hidden rounded-2xl border border-dark-border bg-dark-card"
          >
            <div className="flex flex-col sm:flex-row">
              {/* Car Image */}
              <div className="relative h-36 w-full sm:h-auto sm:w-36 flex-shrink-0">
                {booking.car.images?.[0] ? (
                  <Image
                    src={booking.car.images[0]}
                    alt={booking.car.title}
                    fill
                    className="object-cover"
                  />
                ) : (
                  <div className="flex h-full min-h-[100px] items-center justify-center bg-dark-surface">
                    <Car className="h-8 w-8 text-text-muted" />
                  </div>
                )}
              </div>

              {/* Details */}
              <div className="flex flex-1 flex-col p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-text-primary">
                      {booking.car.title}
                    </h3>
                    <p className="mt-1 text-sm text-text-secondary">
                      {booking.renter?.fullName || booking.renter?.email}
                      {booking.renter?.phone && ` - ${booking.renter.phone}`}
                    </p>
                  </div>
                  {statusBadge(booking.status)}
                </div>

                <div className="mt-3 flex flex-wrap gap-4 text-sm text-text-secondary">
                  <span className="flex items-center gap-1">
                    <CalendarCheck className="h-3.5 w-3.5" />
                    {formatDate(booking.startDate)} → {formatDate(booking.endDate)}
                  </span>
                  <span>
                    {booking.totalDays} {lang === 'ar' ? 'يوم' : 'days'}
                  </span>
                  <span className="font-medium text-status-star">
                    {booking.totalAmount} {t('kwd')}
                  </span>
                </div>

                {/* Actions */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {booking.status === 'APPROVED' && (
                    <button
                      onClick={() => handleStatusChange(booking.id, 'ACTIVE')}
                      disabled={isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-blue-400/10 border border-blue-400/20 px-3 py-1.5 text-xs font-medium text-blue-400 hover:bg-blue-400/20 transition-colors disabled:opacity-50"
                    >
                      <Play className="h-3.5 w-3.5" />
                      {lang === 'ar' ? 'تفعيل' : 'Activate'}
                    </button>
                  )}
                  {booking.status === 'ACTIVE' && (
                    <button
                      onClick={() => handleStatusChange(booking.id, 'COMPLETED')}
                      disabled={isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-emerald-400/10 border border-emerald-400/20 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-400/20 transition-colors disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {lang === 'ar' ? 'إكمال' : 'Complete'}
                    </button>
                  )}
                  {!['COMPLETED', 'CANCELLED', 'REJECTED'].includes(booking.status) && (
                    <button
                      onClick={() => handleStatusChange(booking.id, 'CANCELLED')}
                      disabled={isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-red-400/10 border border-red-400/20 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-400/20 transition-colors disabled:opacity-50"
                    >
                      <Ban className="h-3.5 w-3.5" />
                      {lang === 'ar' ? 'إلغاء' : 'Cancel'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}

        {filteredBookings.length === 0 && (
          <div className="rounded-2xl border border-dark-border bg-dark-card p-12 text-center">
            <CalendarCheck className="mx-auto mb-3 h-12 w-12 text-text-muted" />
            <p className="text-text-secondary">{t('noResults')}</p>
          </div>
        )}
      </div>
    </div>
  )
}
