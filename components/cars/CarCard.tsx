'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { MapPin, Calendar, Users, Fuel, Cog } from 'lucide-react'

interface CarCardProps {
  car: {
    id: string
    title: string
    year: number
    dailyPrice: string | number | { toString: () => string }
    area: string
    city?: string | null
    seats?: number | null
    transmission?: string | null
    images: string[]
    category?: string | null
    owner?: {
      fullName?: string | null
    } | null
  }
}

export function CarCard({ car }: CarCardProps) {
  const { t, lang } = useLanguage()

  const transmissionLabel = car.transmission
    ? car.transmission === 'AUTOMATIC'
      ? t('automatic')
      : car.transmission === 'MANUAL'
        ? t('manual')
        : t('electric')
    : null

  return (
    <Link
      href={`/cars/${car.id}`}
      className="group overflow-hidden rounded-2xl border border-dark-border-light bg-dark-card shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-status-star/30 gold-glow-hover"
    >
      {/* Image */}
      <div className="relative aspect-[16/10] overflow-hidden bg-dark-surface">
        {car.images?.[0] ? (
          <Image
            src={car.images[0]}
            alt={car.title}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-text-muted">
            <Fuel className="h-12 w-12" />
          </div>
        )}

        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-dark-bg/70 via-transparent to-transparent" />

        {/* Price Badge */}
        <div className="absolute bottom-3 start-3 rounded-xl bg-dark-bg/90 px-3 py-2 backdrop-blur-sm border border-dark-border">
          <span className="text-xl font-bold text-status-star">
            {String(car.dailyPrice)}
          </span>
          <span className="ms-1 text-xs text-text-secondary">{t('perDay')}</span>
        </div>

        {/* Category Badge */}
        {car.category && (
          <div className="absolute end-3 top-3 rounded-lg border border-dark-border-light bg-dark-card/90 px-2 py-1 text-xs font-medium text-text-primary backdrop-blur-sm">
            {car.category}
          </div>
        )}
      </div>

      {/* Details */}
      <div className="p-4">
        <h3 className="mb-2 text-lg font-bold text-text-primary line-clamp-1">
          {car.title}
        </h3>

        <div className="flex flex-wrap gap-3 text-sm text-text-secondary">
          <span className="flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5 text-text-secondary" />
            {car.area}
            {car.city && ` - ${car.city}`}
          </span>
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5 text-text-secondary" />
            {car.year}
          </span>
          {car.seats && (
            <span className="flex items-center gap-1">
              <Users className="h-3.5 w-3.5 text-text-secondary" />
              {car.seats}
            </span>
          )}
          {transmissionLabel && (
            <span className="flex items-center gap-1">
              <Cog className="h-3.5 w-3.5 text-text-secondary" />
              {transmissionLabel}
            </span>
          )}
        </div>

        {car.owner?.fullName && (
          <p className="mt-3 border-t border-dark-border pt-3 text-xs text-text-muted">
            {car.owner.fullName}
          </p>
        )}

        {/* Book Now Button */}
        <div className="mt-3 w-full rounded-xl border border-status-star/30 bg-status-star/10 py-2 text-center text-sm font-medium text-status-star transition-all group-hover:bg-status-star group-hover:text-dark-bg">
          {lang === 'ar' ? 'احجز الآن' : 'Book Now'}
        </div>
      </div>
    </Link>
  )
}
