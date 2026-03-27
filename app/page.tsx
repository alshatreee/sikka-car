'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { LegalLinks } from '@/components/legal/LegalModal'
import { CarCard } from '@/components/cars/CarCard'
import { getApprovedCars } from '@/actions/carActions'
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
} from 'lucide-react'

type CarType = Awaited<ReturnType<typeof getApprovedCars>>[number]

export default function HomePage() {
  const { t, lang } = useLanguage()
  const Arrow = lang === 'ar' ? ArrowLeft : ArrowRight
  const [featuredCars, setFeaturedCars] = useState<CarType[]>([])
  const [loadingCars, setLoadingCars] = useState(true)

  useEffect(() => {
    getApprovedCars()
      .then((data) => {
        setFeaturedCars(data.slice(0, 6))
        setLoadingCars(false)
      })
      .catch(() => setLoadingCars(false))
  }, [])

  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-dark-bg">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute -start-20 -top-20 h-96 w-96 rounded-full bg-status-star blur-3xl" />
          <div className="absolute -end-20 bottom-0 h-96 w-96 rounded-full bg-text-secondary blur-3xl" />
        </div>

        <div className="container relative py-20 md:py-32">
          <div className="mx-auto max-w-3xl text-center">
            {/* Badge */}
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-status-star/30 bg-status-star/10 px-4 py-1.5">
              <Star className="h-4 w-4 text-status-star" />
              <span className="text-sm font-medium text-status-star">
                {lang === 'ar' ? 'منصة الكويت الأولى' : "Kuwait's #1 Platform"}
              </span>
            </div>

            <h1 className="mb-6 text-4xl font-black leading-tight text-text-primary md:text-6xl">
              {t('heroTitle')}
            </h1>
            <p className="mb-10 text-lg text-text-secondary md:text-xl">
              {t('heroSubtitle')}
            </p>

            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/browse"
                className="btn-primary flex items-center gap-2 !px-8 !py-4 text-lg"
              >
                {t('browseNow')}
                <Arrow className="h-5 w-5" />
              </Link>
              <Link
                href="/list"
                className="flex items-center gap-2 rounded-xl border border-dark-border bg-dark-surface px-8 py-4 text-lg font-medium text-text-primary backdrop-blur-sm transition-all hover:bg-dark-border"
              >
                <Car className="h-5 w-5" />
                {t('listYourCar')}
              </Link>
            </div>

            {/* Stats */}
            <div className="mt-16 grid grid-cols-3 gap-8">
              {[
                {
                  icon: Car,
                  value: '500+',
                  label: lang === 'ar' ? 'سيارة متاحة' : 'Cars Available',
                },
                {
                  icon: Users,
                  value: '2,000+',
                  label: lang === 'ar' ? 'مستخدم نشط' : 'Active Users',
                },
                {
                  icon: MapPin,
                  value: '6',
                  label: lang === 'ar' ? 'محافظات' : 'Governorates',
                },
              ].map((stat, i) => (
                <div key={i} className="text-center">
                  <stat.icon className="mx-auto mb-2 h-6 w-6 text-status-star" />
                  <div className="text-2xl font-bold text-text-primary md:text-3xl">
                    {stat.value}
                  </div>
                  <div className="text-sm text-text-secondary">{stat.label}</div>
                </div>
              ))}
            </div>
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
