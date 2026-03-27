'use client'

import Image from 'next/image'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { updateCarStatus } from '@/actions/adminActions'
import { useState, useTransition } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  CheckCircle2,
  XCircle,
  Clock,
  Car,
  MapPin,
  Calendar,
  Eye,
} from 'lucide-react'
import Link from 'next/link'

interface AdminCar {
  id: string
  title: string
  brand?: string | null
  model?: string | null
  year: number
  dailyPrice: string
  area: string
  category?: string | null
  status: string
  images: string[]
  createdAt: string
  owner?: {
    fullName?: string | null
    email?: string | null
    phone?: string | null
  } | null
  _count: { bookings: number }
}

export default function AdminCarsClient({ cars: initialCars }: { cars: AdminCar[] }) {
  const { t, lang } = useLanguage()
  const searchParams = useSearchParams()
  const initialStatus = searchParams.get('status') || ''
  const [statusFilter, setStatusFilter] = useState(initialStatus)
  const [cars, setCars] = useState(initialCars)
  const [isPending, startTransition] = useTransition()

  const filteredCars = statusFilter
    ? cars.filter((c) => c.status === statusFilter)
    : cars

  const handleStatusChange = (carId: string, newStatus: 'APPROVED' | 'REJECTED') => {
    startTransition(async () => {
      await updateCarStatus(carId, newStatus)
      setCars((prev) =>
        prev.map((c) => (c.id === carId ? { ...c, status: newStatus } : c))
      )
    })
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-status-warning/10 border border-status-warning/20 px-2.5 py-1 text-xs font-medium text-status-warning">
            <Clock className="h-3 w-3" />
            {t('pendingReview')}
          </span>
        )
      case 'APPROVED':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-status-success/10 border border-status-success/20 px-2.5 py-1 text-xs font-medium text-status-success">
            <CheckCircle2 className="h-3 w-3" />
            {t('approved')}
          </span>
        )
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-400/10 border border-red-400/20 px-2.5 py-1 text-xs font-medium text-red-400">
            <XCircle className="h-3 w-3" />
            {t('rejected')}
          </span>
        )
    }
  }

  const filters = [
    { value: '', label: t('adminAllCars') },
    { value: 'PENDING', label: t('pendingReview') },
    { value: 'APPROVED', label: t('approved') },
    { value: 'REJECTED', label: t('rejected') },
  ]

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-text-primary">
        {t('adminCars')}
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
        {filteredCars.length} {lang === 'ar' ? 'سيارة' : 'cars'}
      </p>

      {/* Cars List */}
      <div className="space-y-4">
        {filteredCars.map((car) => (
          <div
            key={car.id}
            className="overflow-hidden rounded-2xl border border-dark-border bg-dark-card"
          >
            <div className="flex flex-col sm:flex-row">
              {/* Image */}
              <div className="relative h-48 w-full sm:h-auto sm:w-48 flex-shrink-0">
                {car.images?.[0] ? (
                  <Image
                    src={car.images[0]}
                    alt={car.title}
                    fill
                    className="object-cover"
                  />
                ) : (
                  <div className="flex h-full min-h-[120px] items-center justify-center bg-dark-surface">
                    <Car className="h-10 w-10 text-text-muted" />
                  </div>
                )}
              </div>

              {/* Details */}
              <div className="flex flex-1 flex-col p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-bold text-text-primary">
                      {car.title}
                    </h3>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-text-secondary">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3.5 w-3.5" />
                        {car.area}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        {car.year}
                      </span>
                      <span className="font-medium text-status-star">
                        {car.dailyPrice} {t('kwd')}
                      </span>
                    </div>
                  </div>
                  {statusBadge(car.status)}
                </div>

                {/* Owner Info */}
                <div className="mt-3 rounded-xl bg-dark-surface p-3 text-sm">
                  <p className="text-text-secondary">
                    <strong className="text-text-primary">
                      {lang === 'ar' ? 'المالك:' : 'Owner:'}
                    </strong>{' '}
                    {car.owner?.fullName || '-'} ({car.owner?.email})
                  </p>
                  {car.owner?.phone && (
                    <p className="text-text-secondary">
                      <strong className="text-text-primary">
                        {lang === 'ar' ? 'الهاتف:' : 'Phone:'}
                      </strong>{' '}
                      {car.owner.phone}
                    </p>
                  )}
                  <p className="text-text-muted mt-1">
                    {car._count.bookings} {lang === 'ar' ? 'حجز' : 'bookings'}
                  </p>
                </div>

                {/* Actions */}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Link
                    href={`/cars/${car.id}`}
                    target="_blank"
                    className="inline-flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary hover:bg-dark-surface transition-colors"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    {lang === 'ar' ? 'عرض' : 'View'}
                  </Link>

                  {car.status !== 'APPROVED' && (
                    <button
                      onClick={() => handleStatusChange(car.id, 'APPROVED')}
                      disabled={isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-status-success/10 border border-status-success/20 px-3 py-1.5 text-xs font-medium text-status-success hover:bg-status-success/20 transition-colors disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {t('adminApprove')}
                    </button>
                  )}

                  {car.status !== 'REJECTED' && (
                    <button
                      onClick={() => handleStatusChange(car.id, 'REJECTED')}
                      disabled={isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-red-400/10 border border-red-400/20 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-400/20 transition-colors disabled:opacity-50"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      {t('adminReject')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}

        {filteredCars.length === 0 && (
          <div className="rounded-2xl border border-dark-border bg-dark-card p-12 text-center">
            <Car className="mx-auto mb-3 h-12 w-12 text-text-muted" />
            <p className="text-text-secondary">{t('noResults')}</p>
          </div>
        )}
      </div>
    </div>
  )
}
