'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { BookingPanel } from '@/components/cars/BookingPanel'
import {
  MapPin,
  Calendar,
  Users,
  Cog,
  Car,
  ChevronLeft,
  ChevronRight,
  Phone,
  Mail,
  Shield,
  Clock,
  Cigarette,
  Gauge,
  UserCheck,
} from 'lucide-react'

interface CarDetailClientProps {
  car: {
    id: string
    title: string
    titleEn?: string | null
    brand?: string | null
    model?: string | null
    year: number
    dailyPrice: string
    area: string
    city?: string | null
    origin?: string | null
    type?: string | null
    category?: string | null
    seats?: number | null
    transmission?: string | null
    smokingPolicy?: string | null
    distancePolicy?: string | null
    minAge?: number | null
    availabilityText?: string | null
    notes?: string | null
    images: string[]
    owner?: {
      fullName?: string | null
      email?: string | null
      phone?: string | null
    } | null
  }
  currentUser: {
    fullName: string
    email: string
  } | null
}

export default function CarDetailClient({
  car,
  currentUser,
}: CarDetailClientProps) {
  const { t, lang } = useLanguage()
  const [currentImage, setCurrentImage] = useState(0)

  const transmissionLabel = car.transmission
    ? car.transmission === 'AUTOMATIC'
      ? t('automatic')
      : car.transmission === 'MANUAL'
        ? t('manual')
        : t('electric')
    : null

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="grid gap-8 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Image Gallery */}
          <div className="relative mb-6 overflow-hidden rounded-2xl bg-dark-surface">
            <div className="aspect-[16/10]">
              {car.images?.[currentImage] ? (
                <Image
                  src={car.images[currentImage]}
                  alt={car.title}
                  fill
                  className="object-cover"
                  priority
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <Car className="h-24 w-24 text-text-muted" />
                </div>
              )}
            </div>

            {car.images.length > 1 && (
              <>
                <button
                  onClick={() =>
                    setCurrentImage((prev) =>
                      prev > 0 ? prev - 1 : car.images.length - 1
                    )
                  }
                  className="absolute start-3 top-1/2 -translate-y-1/2 rounded-full bg-dark-card/90 p-2 shadow-lg transition-all hover:bg-dark-card border border-dark-border"
                >
                  {lang === 'ar' ? (
                    <ChevronRight className="h-5 w-5 text-text-primary" />
                  ) : (
                    <ChevronLeft className="h-5 w-5 text-text-primary" />
                  )}
                </button>
                <button
                  onClick={() =>
                    setCurrentImage((prev) =>
                      prev < car.images.length - 1 ? prev + 1 : 0
                    )
                  }
                  className="absolute end-3 top-1/2 -translate-y-1/2 rounded-full bg-dark-card/90 p-2 shadow-lg transition-all hover:bg-dark-card border border-dark-border"
                >
                  {lang === 'ar' ? (
                    <ChevronLeft className="h-5 w-5 text-text-primary" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-text-primary" />
                  )}
                </button>

                <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-1.5">
                  {car.images.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setCurrentImage(i)}
                      className={`h-2 rounded-full transition-all ${
                        i === currentImage
                          ? 'w-6 bg-status-star'
                          : 'w-2 bg-dark-border hover:bg-dark-border-light'
                      }`}
                    />
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Thumbnails */}
          {car.images.length > 1 && (
            <div className="mb-6 flex gap-2 overflow-x-auto pb-2">
              {car.images.map((img, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentImage(i)}
                  className={`relative h-16 w-20 flex-shrink-0 overflow-hidden rounded-xl transition-all ${
                    i === currentImage
                      ? 'ring-2 ring-status-star ring-offset-2 ring-offset-dark-bg'
                      : 'opacity-60 hover:opacity-100'
                  }`}
                >
                  <Image
                    src={img}
                    alt={`${car.title} ${i + 1}`}
                    fill
                    className="object-cover"
                  />
                </button>
              ))}
            </div>
          )}

          {/* Car Info */}
          <div className="card mb-6">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h1 className="mb-1 text-2xl font-bold text-text-primary">
                  {car.title}
                </h1>
                {car.titleEn && (
                  <p className="text-sm text-text-secondary">{car.titleEn}</p>
                )}
              </div>
              <div className="text-end">
                <div className="text-2xl font-bold text-status-star">
                  {String(car.dailyPrice)}
                </div>
                <div className="text-sm text-text-secondary">{t('perDay')}</div>
              </div>
            </div>

            {car.category && (
              <span className="mb-4 inline-block rounded-full border border-dark-border-light bg-dark-surface px-3 py-1 text-xs font-medium text-text-primary">
                {car.category}
              </span>
            )}

            {/* Specs Grid */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
              <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                <MapPin className="h-5 w-5 text-text-secondary" />
                <div>
                  <div className="text-xs text-text-secondary">{t('area')}</div>
                  <div className="text-sm font-medium text-text-primary">
                    {car.area}
                    {car.city && ` - ${car.city}`}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                <Calendar className="h-5 w-5 text-text-secondary" />
                <div>
                  <div className="text-xs text-text-secondary">{t('year')}</div>
                  <div className="text-sm font-medium text-text-primary">{car.year}</div>
                </div>
              </div>

              {car.seats && (
                <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                  <Users className="h-5 w-5 text-text-secondary" />
                  <div>
                    <div className="text-xs text-text-secondary">{t('seats')}</div>
                    <div className="text-sm font-medium text-text-primary">{car.seats}</div>
                  </div>
                </div>
              )}

              {transmissionLabel && (
                <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                  <Cog className="h-5 w-5 text-text-secondary" />
                  <div>
                    <div className="text-xs text-text-secondary">
                      {t('transmission')}
                    </div>
                    <div className="text-sm font-medium text-text-primary">
                      {transmissionLabel}
                    </div>
                  </div>
                </div>
              )}

              {car.smokingPolicy && (
                <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                  <Cigarette className="h-5 w-5 text-text-secondary" />
                  <div>
                    <div className="text-xs text-text-secondary">
                      {t('smokingPolicy')}
                    </div>
                    <div className="text-sm font-medium text-text-primary">
                      {car.smokingPolicy}
                    </div>
                  </div>
                </div>
              )}

              {car.distancePolicy && (
                <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                  <Gauge className="h-5 w-5 text-text-secondary" />
                  <div>
                    <div className="text-xs text-text-secondary">
                      {t('distancePolicy')}
                    </div>
                    <div className="text-sm font-medium text-text-primary">
                      {car.distancePolicy}
                    </div>
                  </div>
                </div>
              )}

              {car.minAge && (
                <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                  <UserCheck className="h-5 w-5 text-text-secondary" />
                  <div>
                    <div className="text-xs text-text-secondary">{t('minAge')}</div>
                    <div className="text-sm font-medium text-text-primary">{car.minAge}+</div>
                  </div>
                </div>
              )}

              {car.availabilityText && (
                <div className="flex items-center gap-3 rounded-xl bg-dark-surface p-3 border border-dark-border">
                  <Clock className="h-5 w-5 text-text-secondary" />
                  <div>
                    <div className="text-xs text-text-secondary">
                      {t('availability')}
                    </div>
                    <div className="text-sm font-medium text-text-primary">
                      {car.availabilityText}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {car.notes && (
              <div className="mt-4 rounded-xl bg-status-warning/10 p-4 border border-status-warning/20">
                <p className="text-sm text-status-warning">
                  <strong>{t('notes')}:</strong> {car.notes}
                </p>
              </div>
            )}
          </div>

          {/* Owner Info */}
          {car.owner && (
            <div className="card">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
                <Shield className="h-5 w-5 text-status-star" />
                {lang === 'ar' ? 'معلومات المالك' : 'Owner Information'}
              </h2>
              <div className="space-y-2">
                {car.owner.fullName && (
                  <p className="text-sm text-text-primary">
                    <strong>{car.owner.fullName}</strong>
                  </p>
                )}
                {car.owner.email && (
                  <p className="flex items-center gap-2 text-sm text-text-secondary">
                    <Mail className="h-4 w-4" />
                    {car.owner.email}
                  </p>
                )}
                {car.owner.phone && (
                  <p className="flex items-center gap-2 text-sm text-text-secondary">
                    <Phone className="h-4 w-4" />
                    {car.owner.phone}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar - Booking Panel */}
        <div className="lg:col-span-1">
          <div className="sticky top-24">
            {currentUser ? (
              <BookingPanel
                carId={car.id}
                dailyPrice={Number(car.dailyPrice)}
                customerName={currentUser.fullName}
                customerEmail={currentUser.email}
              />
            ) : (
              <div className="card text-center">
                <Car className="mx-auto mb-3 h-12 w-12 text-gray-300" />
                <p className="mb-4 text-gray-500">
                  {lang === 'ar'
                    ? 'سجّل دخولك لحجز هذه السيارة'
                    : 'Sign in to book this car'}
                </p>
                <Link href="/sign-in" className="btn-primary inline-block">
                  {t('signIn')}
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
