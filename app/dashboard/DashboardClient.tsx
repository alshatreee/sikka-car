'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import Image from 'next/image'
import {
  Car,
  CheckCircle,
  Clock,
  XCircle,
  PlusCircle,
  Calendar,
  CreditCard,
  MapPin,
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
  }>
}

const statusConfig: Record<
  string,
  { color: string; bg: string; icon: typeof CheckCircle; label: { ar: string; en: string } }
> = {
  APPROVED: {
    color: 'text-status-success',
    bg: 'bg-status-success/10',
    icon: CheckCircle,
    label: { ar: 'معتمدة', en: 'Approved' },
  },
  PENDING: {
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    icon: Clock,
    label: { ar: 'قيد المراجعة', en: 'Pending' },
  },
  REJECTED: {
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    icon: XCircle,
    label: { ar: 'مرفوضة', en: 'Rejected' },
  },
  AWAITING_PAYMENT: {
    color: 'text-text-secondary',
    bg: 'bg-dark-surface',
    icon: CreditCard,
    label: { ar: 'بانتظار الدفع', en: 'Awaiting Payment' },
  },
  ACTIVE: {
    color: 'text-status-success',
    bg: 'bg-status-success/10',
    icon: CheckCircle,
    label: { ar: 'نشط', en: 'Active' },
  },
  COMPLETED: {
    color: 'text-text-secondary',
    bg: 'bg-dark-surface',
    icon: CheckCircle,
    label: { ar: 'مكتمل', en: 'Completed' },
  },
  CANCELLED: {
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    icon: XCircle,
    label: { ar: 'ملغي', en: 'Cancelled' },
  },
}

export default function DashboardClient({
  cars,
  bookings,
}: DashboardClientProps) {
  const { t, lang } = useLanguage()

  const totalApproved = cars.filter((c) => c.status === 'APPROVED').length
  const totalPending = cars.filter((c) => c.status === 'PENDING').length
  const totalRejected = cars.filter((c) => c.status === 'REJECTED').length

  function StatusBadge({ status }: { status: string }) {
    const config = statusConfig[status] || statusConfig.PENDING
    const Icon = config.icon
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${config.bg} ${config.color}`}
      >
        <Icon className="h-3 w-3" />
        {config.label[lang]}
      </span>
    )
  }

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
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: t('totalCars'),
            value: cars.length,
            icon: Car,
          },
          {
            label: t('approved'),
            value: totalApproved,
            icon: CheckCircle,
          },
          {
            label: t('pendingReview'),
            value: totalPending,
            icon: Clock,
          },
          {
            label: t('rejected'),
            value: totalRejected,
            icon: XCircle,
          },
        ].map((stat, i) => (
          <div
            key={i}
            className="card flex items-center gap-4"
          >
            <div
              className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-dark-surface border border-dark-border-light shadow-lg`}
            >
              <stat.icon className="h-6 w-6 text-status-star" />
            </div>
            <div>
              <div className="text-2xl font-bold text-text-primary">
                {stat.value}
              </div>
              <div className="text-sm text-text-secondary">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* My Cars */}
      <section className="mb-10">
        <h2 className="mb-4 text-xl font-bold text-text-primary">
          {lang === 'ar' ? 'سياراتي' : 'My Cars'}
        </h2>

        {cars.length === 0 ? (
          <div className="card flex flex-col items-center py-12 text-center">
            <Car className="mb-4 h-12 w-12 text-text-muted" />
            <p className="mb-4 text-text-secondary">
              {lang === 'ar'
                ? 'لم تضف أي سيارة بعد'
                : "You haven't listed any cars yet"}
            </p>
            <Link href="/list" className="btn-primary">
              {t('listCar')}
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cars.map((car) => (
              <div key={car.id} className="card overflow-hidden !p-0">
                <div className="relative aspect-[16/9] bg-dark-surface">
                  {car.images?.[0] ? (
                    <Image
                      src={car.images[0]}
                      alt={car.title}
                      fill
                      className="object-cover"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center">
                      <Car className="h-8 w-8 text-text-muted" />
                    </div>
                  )}
                </div>
                <div className="p-4">
                  <div className="mb-2 flex items-start justify-between">
                    <h3 className="font-bold text-text-primary line-clamp-1">
                      {car.title}
                    </h3>
                    <StatusBadge status={car.status} />
                  </div>
                  <div className="flex items-center gap-3 text-sm text-text-secondary">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {car.area}
                    </span>
                    <span className="font-medium text-status-star">
                      {String(car.dailyPrice)} {t('perDay')}
                    </span>
                  </div>

                  {car.bookings.length > 0 && (
                    <div className="mt-3 border-t border-dark-border pt-3">
                      <p className="text-xs font-medium text-text-secondary">
                        {lang === 'ar'
                          ? `${car.bookings.length} حجوزات`
                          : `${car.bookings.length} bookings`}
                      </p>
                    </div>
                  )}
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
              {lang === 'ar'
                ? 'لا توجد حجوزات حتى الآن'
                : 'No bookings yet'}
            </p>
            <Link href="/browse" className="btn-primary">
              {t('browseNow')}
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {bookings.map((booking) => (
              <div key={booking.id} className="card flex gap-4">
                <div className="relative h-20 w-28 flex-shrink-0 overflow-hidden rounded-xl bg-dark-surface">
                  {booking.car.images?.[0] ? (
                    <Image
                      src={booking.car.images[0]}
                      alt={booking.car.title}
                      fill
                      className="object-cover"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center">
                      <Car className="h-6 w-6 text-text-muted" />
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="mb-1 flex items-start justify-between">
                    <h3 className="font-bold text-text-primary">
                      {booking.car.title}
                    </h3>
                    <StatusBadge status={booking.status} />
                  </div>
                  <div className="flex flex-wrap gap-3 text-sm text-text-secondary">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" />
                      {new Date(booking.startDate).toLocaleDateString(
                        lang === 'ar' ? 'ar-KW' : 'en-US'
                      )}{' '}
                      →{' '}
                      {new Date(booking.endDate).toLocaleDateString(
                        lang === 'ar' ? 'ar-KW' : 'en-US'
                      )}
                    </span>
                    <span className="font-medium text-status-star">
                      {String(booking.totalAmount)} د.ك
                    </span>
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
