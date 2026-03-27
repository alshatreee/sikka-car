'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { LegalLinks } from '@/components/legal/LegalModal'
import { CarCard } from '@/components/cars/CarCard'
import { getApprovedCars } from '@/actions/carActions'
import Image from 'next/image'
import {
  Car,
  Shield,
  CheckCircle,
  Zap,
  ArrowLeft,
  ArrowRight,
  Star,
  Users,
  MapPin,
  Loader2,
  Search,
  Calendar,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

type CarType = Awaited<ReturnType<typeof getApprovedCars>>[number]

export default function HomePage() {
  const { t, lang } = useLanguage()
  const Arrow = lang === 'ar' ? ArrowLeft : ArrowRight
  const [featuredCars, setFeaturedCars] = useState<CarType[]>([])
  const [loadingCars, setLoadingCars] = useState(true)
  const [heroCarIndex, setHeroCarIndex] = useState(0)

  useEffect(() => {
    getApprovedCars()
      .then((data) => {
        setFeaturedCars(data.slice(0, 6))
        setLoadingCars(false)
      })
      .catch(() => setLoadingCars(false))
  }, [])

  const heroCar = featuredCars[heroCarIndex] || null
  const nextHeroCar = () => {
    if (featuredCars.length > 0) setHeroCarIndex((i) => (i + 1) % featuredCars.length)
  }
  const prevHeroCar = () => {
    if (featuredCars.length > 0) setHeroCarIndex((i) => (i - 1 + featuredCars.length) % featuredCars.length)
  }

  return (
    <main className="min-h-screen">
      {/* Hero Section - Split Layout */}
      <section className="relative overflow-hidden bg-dark-bg">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute -start-20 -top-20 h-96 w-96 rounded-full bg-status-star blur-3xl" />
          <div className="absolute -end-20 bottom-0 h-96 w-96 rounded-full bg-text-secondary blur-3xl" />
        </div>

        <div className="container relative py-12 md:py-20">
          {/* Badge */}
          <div className="mb-8 flex justify-start">
            <div className="inline-flex items-center gap-2 rounded-full border border-status-star/30 bg-status-star/10 px-4 py-1.5">
              <Star className="h-4 w-4 text-status-star" />
              <span className="text-sm font-medium text-status-star">
                {lang === 'ar' ? 'منصة موثوقة لتأجير السيارات' : 'Trusted Car Rental Platform'}
              </span>
            </div>
          </div>

          <div className="grid items-start gap-10 md:grid-cols-2">
            {/* Text Content - appears first in DOM so it's on the right in RTL (Arabic) and left in LTR (English) */}
            <div className="text-start">
              <h1 className="mb-6 text-4xl font-black leading-tight text-text-primary md:text-5xl lg:text-6xl">
                {lang === 'ar'
                  ? 'حوّل سيارتك إلى دخل إضافي بثقة وسهولة'
                  : 'Turn Your Car Into Extra Income with Trust'}
              </h1>
              <p className="mb-8 text-base text-text-secondary md:text-lg leading-relaxed">
                {lang === 'ar'
                  ? 'Sikka Car منصة كويتية تربط بين ملاك السيارات والأشخاص الباحثين عن استئجارها، ضمن تجربة رقمية واضحة وآمنة تساعد على الحجز السريع، وتمنح المالك وسيلة عملية للاستفادة من سيارته.'
                  : 'Sikka Car is a Kuwaiti platform connecting car owners with renters through a clear, secure digital experience for quick booking.'}
              </p>
              <p className="mb-8 text-sm text-text-muted">
                {lang === 'ar'
                  ? 'تجربة واضحة وآمنة تبدأ من البحث حتى استلام السيارة.'
                  : 'A clear and safe experience from search to car pickup.'}
              </p>

              <div className="flex flex-wrap gap-3 justify-start">
                <Link
                  href="/browse"
                  className="btn-primary flex items-center gap-2 !px-6 !py-3"
                >
                  {t('browseNow')}
                  <Arrow className="h-5 w-5" />
                </Link>
                <Link
                  href="/list"
                  className="flex items-center gap-2 rounded-xl border border-dark-border bg-dark-surface px-6 py-3 font-medium text-text-primary backdrop-blur-sm transition-all hover:bg-dark-border"
                >
                  <Car className="h-5 w-5" />
                  {lang === 'ar' ? 'ضيف سيارتك' : 'List Your Car'}
                </Link>
              </div>
            </div>

            {/* Car Showcase Card - appears second in DOM so it's on the left in RTL (Arabic) and right in LTR (English) */}
            <div>
              <div className="overflow-hidden rounded-2xl border border-dark-border bg-dark-card shadow-2xl">
                {/* Card Header */}
                <div className="flex items-center justify-between border-b border-dark-border px-5 py-3">
                  <span className="text-sm font-bold text-text-primary">Sikka Car</span>
                  <div className="flex items-center gap-2">
                    <span className="rounded-lg bg-dark-surface px-3 py-1 text-xs font-medium text-status-star border border-dark-border-light">
                      {lang === 'ar' ? 'سيارات مميزة' : 'Featured'}
                    </span>
                  </div>
                </div>

                {/* Car Image Area */}
                <div className="relative aspect-[16/10] bg-dark-surface">
                  {heroCar?.images?.[0] ? (
                    <Image
                      src={heroCar.images[0]}
                      alt={heroCar.title}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center">
                      <div className="text-center">
                        <Car className="mx-auto mb-2 h-12 w-12 text-text-muted" />
                        <p className="text-sm text-text-muted">
                          {lang === 'ar' ? 'عرض بصري فاخر للسيارات' : 'Premium car showcase'}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Price Badge */}
                  {heroCar && (
                    <div className="absolute bottom-3 start-3 rounded-xl bg-dark-bg/90 px-3 py-1.5 backdrop-blur-sm border border-dark-border">
                      <span className="text-lg font-bold text-status-star">
                        {String(heroCar.dailyPrice)}
                      </span>
                      <span className="ms-1 text-xs text-text-secondary">
                        {lang === 'ar' ? 'د.ك / يوم' : 'KD/day'}
                      </span>
                    </div>
                  )}

                  {/* Category Badge */}
                  {heroCar?.category && (
                    <div className="absolute end-3 top-3 rounded-lg border border-dark-border-light bg-dark-card/90 px-2 py-1 text-xs font-medium text-text-primary backdrop-blur-sm">
                      {heroCar.category}
                    </div>
                  )}

                  {/* Navigation Arrows */}
                  {featuredCars.length > 1 && (
                    <>
                      <button
                        onClick={prevHeroCar}
                        className="absolute start-2 top-1/2 -translate-y-1/2 rounded-full bg-dark-bg/70 p-1.5 text-text-primary backdrop-blur-sm transition hover:bg-dark-bg border border-dark-border"
                      >
                        {lang === 'ar' ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                      </button>
                      <button
                        onClick={nextHeroCar}
                        className="absolute end-2 top-1/2 -translate-y-1/2 rounded-full bg-dark-bg/70 p-1.5 text-text-primary backdrop-blur-sm transition hover:bg-dark-bg border border-dark-border"
                      >
                        {lang === 'ar' ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                    </>
                  )}
                </div>

                {/* Car Info */}
                {heroCar && (
                  <div className="border-t border-dark-border px-5 py-3">
                    <h3 className="mb-1 text-sm font-bold text-text-primary">{heroCar.title}</h3>
                    <div className="flex items-center gap-3 text-xs text-text-secondary">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" /> {heroCar.area}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" /> {heroCar.year}
                      </span>
                      {heroCar.seats && (
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" /> {heroCar.seats}
                        </span>
                      )}
                    </div>
                    {/* Dots indicator */}
                    <div className="mt-2 flex justify-center gap-1.5">
                      {featuredCars.slice(0, 6).map((_, i) => (
                        <button
                          key={i}
                          onClick={() => setHeroCarIndex(i)}
                          className={`h-1.5 rounded-full transition-all ${i === heroCarIndex ? 'w-4 bg-status-star' : 'w-1.5 bg-dark-border-light'}`}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Search Bar */}
                <div className="border-t border-dark-border bg-dark-surface px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex flex-1 items-center gap-2 rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-xs text-text-secondary">
                      <MapPin className="h-3.5 w-3.5 text-text-muted" />
                      <span>{lang === 'ar' ? 'كل المناطق' : 'All Areas'}</span>
                    </div>
                    <div className="flex flex-1 items-center gap-2 rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-xs text-text-secondary">
                      <Car className="h-3.5 w-3.5 text-text-muted" />
                      <span>{lang === 'ar' ? 'الفئة' : 'Category'}</span>
                    </div>
                    <div className="flex flex-1 items-center gap-2 rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-xs text-text-secondary">
                      <Calendar className="h-3.5 w-3.5 text-text-muted" />
                      <span>{lang === 'ar' ? 'التاريخ' : 'Date'}</span>
                    </div>
                    <Link
                      href="/browse"
                      className="rounded-lg bg-text-primary px-3 py-2 text-dark-bg transition hover:bg-text-secondary"
                    >
                      <Search className="h-4 w-4" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* Stats Bar */}
          <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { value: '500+', label: lang === 'ar' ? 'سيارة معروضة' : 'Cars Listed', color: 'text-status-star' },
              { value: '2K+', label: lang === 'ar' ? 'مستخدم' : 'Users', color: 'text-text-primary' },
              { value: '4.9★', label: lang === 'ar' ? 'تقييم' : 'Rating', color: 'text-status-star' },
              { value: '20%', label: lang === 'ar' ? 'عمولة' : 'Commission', color: 'text-text-primary' },
            ].map((stat, i) => (
              <div
                key={i}
                className="rounded-xl border border-dark-border bg-dark-card px-4 py-3 text-center"
              >
                <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                <div className="text-xs text-text-secondary">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Cars */}
      <section className="bg-dark-card border-t border-dark-border py-20">
        <div className="container">
          <div className="mb-10 flex items-center justify-between">
            <h2 className="text-3xl font-bold text-text-primary">
              {lang === 'ar' ? 'سيارات مميزة' : 'Featured Cars'}
            </h2>
            <Link
              href="/browse"
              className="flex items-center gap-1 text-status-star transition-colors hover:text-status-star/80"
            >
              {lang === 'ar' ? 'عرض الكل' : 'View All'}
              <Arrow className="h-4 w-4" />
            </Link>
          </div>

          {loadingCars ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-text-secondary" />
            </div>
          ) : featuredCars.length > 0 ? (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {featuredCars.map((car) => (
                <CarCard key={car.id} car={{ ...car, dailyPrice: String(car.dailyPrice) }} />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dark-border bg-dark-bg p-12 text-center">
              <Car className="mx-auto mb-4 h-12 w-12 text-text-muted" />
              <p className="text-lg text-text-secondary">
                {lang === 'ar' ? 'لا توجد سيارات متاحة حالياً' : 'No cars available yet'}
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Why Choose Us */}
      <section className="py-20">
        <div className="container">
          <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">
            {t('whyChooseUs')}
          </h2>

          <div className="grid gap-8 md:grid-cols-3">
            {[
              {
                icon: Shield,
                title: t('securePayments'),
                desc: t('securePaymentsDesc'),
              },
              {
                icon: CheckCircle,
                title: t('verifiedCars'),
                desc: t('verifiedCarsDesc'),
              },
              {
                icon: Zap,
                title: t('easyBooking'),
                desc: t('easyBookingDesc'),
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="group rounded-2xl border border-dark-border bg-dark-card p-8 text-center shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl"
              >
                <div
                  className={`mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-surface border border-dark-border-light shadow-lg`}
                >
                  <feature.icon className="h-7 w-7 text-status-star" />
                </div>
                <h3 className="mb-3 text-xl font-bold text-text-primary">
                  {feature.title}
                </h3>
                <p className="text-text-secondary">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-dark-bg py-20">
        <div className="container">
          <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'كيف يعمل سكة كار؟' : 'How Sikka Car Works?'}
          </h2>

          <div className="grid gap-8 md:grid-cols-4">
            {[
              {
                step: '1',
                title: lang === 'ar' ? 'اختر سيارتك' : 'Choose Your Car',
                desc:
                  lang === 'ar'
                    ? 'تصفح مئات السيارات المتاحة في منطقتك'
                    : 'Browse hundreds of available cars in your area',
              },
              {
                step: '2',
                title: lang === 'ar' ? 'حدد التواريخ' : 'Select Dates',
                desc:
                  lang === 'ar'
                    ? 'اختر تاريخ البداية والنهاية وأوقات الاستلام والتسليم'
                    : 'Choose start and end dates with pickup and drop-off times',
              },
              {
                step: '3',
                title: lang === 'ar' ? 'ادفع بأمان' : 'Pay Securely',
                desc:
                  lang === 'ar'
                    ? 'أكمل الدفع عبر K-Net أو Visa أو Apple Pay'
                    : 'Complete payment via K-Net, Visa, or Apple Pay',
              },
              {
                step: '4',
                title: lang === 'ar' ? 'استلم سيارتك' : 'Get Your Car',
                desc:
                  lang === 'ar'
                    ? 'استلم السيارة من المالك واستمتع برحلتك'
                    : 'Pick up the car from the owner and enjoy your ride',
              },
            ].map((item, i) => (
              <div key={i} className="text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-dark-card border border-dark-border-light text-xl font-bold text-status-star shadow-lg">
                  {item.step}
                </div>
                <h3 className="mb-2 text-lg font-bold text-text-primary">
                  {item.title}
                </h3>
                <p className="text-sm text-text-secondary">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-dark-card border-t border-dark-border py-16">
        <div className="container text-center">
          <h2 className="mb-4 text-3xl font-bold text-text-primary">
            {lang === 'ar'
              ? 'عندك سيارة؟ حوّلها لمصدر دخل!'
              : 'Have a Car? Turn it into Income!'}
          </h2>
          <p className="mb-8 text-lg text-text-secondary">
            {lang === 'ar'
              ? 'سجّل سيارتك على سكة كار وابدأ بكسب المال من سيارتك المتوقفة'
              : 'List your car on Sikka Car and start earning from your parked car'}
          </p>
          <Link
            href="/list"
            className="inline-flex items-center gap-2 rounded-xl bg-brand-solid px-8 py-4 text-lg font-bold text-text-primary shadow-2xl transition-all hover:-translate-y-0.5 hover:shadow-3xl hover:bg-brand-solid-hover"
          >
            {t('listYourCar')}
            <Arrow className="h-5 w-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-dark-bg border-t border-dark-border py-10">
        <div className="container text-center">
          <div className="mb-4 flex items-center justify-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-dark-card border border-dark-border">
              <Car className="h-4 w-4 text-status-star" />
            </div>
            <span className="text-lg font-bold text-text-primary">
              Sikka <span className="text-status-star">Car</span>
            </span>
          </div>
          <p className="mb-4 text-sm text-text-secondary">{t('copyright')}</p>
          <LegalLinks />
        </div>
      </footer>
    </main>
  )
}
