'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
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
  Instagram,
  Twitter,
  Quote,
  Wallet,
  Clock,
  Heart,
  Phone,
  Mail,
} from 'lucide-react'

type CarType = Awaited<ReturnType<typeof getApprovedCars>>[number]

function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsVisible(true) },
      { threshold: 0.15 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  return { ref, isVisible }
}

function CountUp({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [count, setCount] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !started.current) {
        started.current = true
        const duration = 1500
        const steps = 40
        const increment = target / steps
        let current = 0
        const timer = setInterval(() => {
          current += increment
          if (current >= target) { setCount(target); clearInterval(timer) }
          else setCount(Math.floor(current))
        }, duration / steps)
      }
    }, { threshold: 0.5 })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [target])

  return <span ref={ref}>{count}{suffix}</span>
}

export default function HomePage() {
  const { t, lang } = useLanguage()
  const Arrow = lang === 'ar' ? ArrowLeft : ArrowRight
  const [featuredCars, setFeaturedCars] = useState<CarType[]>([])
  const [loadingCars, setLoadingCars] = useState(true)
  const [heroCarIndex, setHeroCarIndex] = useState(0)

  const section1 = useScrollReveal()
  const section2 = useScrollReveal()
  const section3 = useScrollReveal()
  const section4 = useScrollReveal()
  const section5 = useScrollReveal()

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
            {/* Text Content */}
            <div className="text-start animate-hero-text">
              <h1 className="mb-6 text-3xl font-bold leading-relaxed text-text-primary md:text-4xl md:leading-relaxed lg:text-5xl lg:leading-relaxed">
                {lang === 'ar'
                  ? 'حوّل سيارتك إلى دخل إضافي بثقة وسهولة'
                  : 'Turn Your Car Into Extra Income with Trust'}
              </h1>
              <p className="mb-8 text-base text-text-secondary md:text-lg leading-relaxed">
                {lang === 'ar'
                  ? 'منصة كويتية موثوقة تربط ملاك السيارات بالمستأجرين ضمن تجربة واضحة وآمنة وسهلة الحجز'
                  : 'A trusted Kuwaiti platform connecting car owners with renters — easy, secure, and seamless.'}
              </p>

              <div className="flex flex-wrap gap-3 justify-start">
                <Link
                  href="/browse"
                  className="flex items-center gap-2 rounded-xl border-2 border-status-star px-6 py-3 font-medium text-status-star transition-all hover:bg-status-star hover:text-dark-bg"
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

            {/* Car Showcase Card */}
            <div className="animate-hero-card">
              <div className="overflow-hidden rounded-2xl border border-dark-border-light bg-dark-card shadow-[0_0_30px_rgba(255,184,0,0.08)] shadow-2xl">
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
                      className="rounded-lg bg-status-star px-3 py-2 text-dark-bg transition hover:bg-status-star/90"
                    >
                      <Search className="h-4 w-4" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* Stats Bar */}
          <div className="mt-12 grid grid-cols-3 gap-4 animate-hero-stats">
            {[
              { target: 500, suffix: '+', label: lang === 'ar' ? 'سيارة معروضة' : 'Cars Listed', icon: Car },
              { target: 2000, suffix: '+', label: lang === 'ar' ? 'مستخدم' : 'Users', icon: Users },
              { target: 4.9, suffix: '★', label: lang === 'ar' ? 'تقييم' : 'Rating', icon: Star, decimal: true },
            ].map((stat, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-xl border border-dark-border-light bg-dark-card/80 px-4 py-3 transition-all duration-500 hover:border-status-star/30"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-status-star/10">
                  <stat.icon className="h-5 w-5 text-status-star" />
                </div>
                <div>
                  <div className="text-xl font-bold text-text-primary">
                    {stat.decimal ? <>{stat.target}{stat.suffix}</> : <CountUp target={stat.target} suffix={stat.suffix} />}
                  </div>
                  <div className="text-xs text-text-secondary">{stat.label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Cars */}
      <section className="bg-darker border-t border-dark-border py-20">
        <div ref={section1.ref} className={`container transition-all duration-700 ${section1.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
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
        <div ref={section2.ref} className={`container transition-all duration-700 ${section2.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
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
                className="group rounded-2xl border border-dark-border bg-dark-card p-8 text-center shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:border-status-star/40"
              >
                <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-status-star/10 border border-status-star/20 transition-all duration-300 group-hover:bg-status-star/20">
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
      <section className="bg-darker py-20">
        <div ref={section3.ref} className={`container transition-all duration-700 ${section3.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'كيف يعمل سكة كار؟' : 'How Sikka Car Works?'}
          </h2>

          <div className="relative grid gap-8 md:grid-cols-4">
            {/* Connecting line */}
            <div className="absolute top-7 hidden h-0.5 bg-gradient-to-r from-status-star/0 via-status-star/30 to-status-star/0 md:block" style={{ left: '12.5%', right: '12.5%' }} />

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
              <div key={i} className="relative text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-status-star text-xl font-bold text-dark-bg shadow-lg shadow-status-star/20">
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

      {/* Testimonials */}
      <section className="bg-dark-card border-t border-dark-border py-20">
        <div ref={section4.ref} className={`container transition-all duration-700 ${section4.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'آراء عملائنا' : 'What Our Users Say'}
          </h2>
          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                name: lang === 'ar' ? 'عبدالله المطيري' : 'Abdullah Al-Mutairi',
                role: lang === 'ar' ? 'مستأجر' : 'Renter',
                text: lang === 'ar'
                  ? 'تجربة ممتازة! حجزت سيارة بسهولة تامة والدفع كان آمن وسريع. أنصح فيها بقوة.'
                  : 'Excellent experience! Booked a car effortlessly, payment was secure and fast. Highly recommended.',
                rating: 5,
              },
              {
                name: lang === 'ar' ? 'فاطمة الشمري' : 'Fatma Al-Shammari',
                role: lang === 'ar' ? 'مالكة سيارة' : 'Car Owner',
                text: lang === 'ar'
                  ? 'سكة كار ساعدتني أحول سيارتي الثانية لمصدر دخل. المنصة سهلة والفريق متعاون.'
                  : 'Sikka Car helped me turn my second car into income. The platform is easy and the team is helpful.',
                rating: 5,
              },
              {
                name: lang === 'ar' ? 'محمد العنزي' : 'Mohammed Al-Enezi',
                role: lang === 'ar' ? 'مستأجر' : 'Renter',
                text: lang === 'ar'
                  ? 'أسعار معقولة وسيارات نظيفة. استأجرت أكثر من مرة ودايم التجربة تكون ممتازة.'
                  : 'Reasonable prices and clean cars. Rented multiple times and the experience is always great.',
                rating: 5,
              },
            ].map((review, i) => (
              <div
                key={i}
                className="rounded-2xl border border-dark-border bg-dark-bg p-6 transition-all duration-300 hover:-translate-y-1 hover:border-status-star/20"
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <Quote className="mb-4 h-6 w-6 text-status-star/40" />
                <p className="mb-4 text-sm leading-relaxed text-text-secondary">{review.text}</p>
                <div className="mb-3 flex gap-0.5">
                  {Array.from({ length: review.rating }).map((_, j) => (
                    <Star key={j} className="h-4 w-4 fill-status-star text-status-star" />
                  ))}
                </div>
                <div className="border-t border-dark-border pt-3">
                  <p className="text-sm font-bold text-text-primary">{review.name}</p>
                  <p className="text-xs text-text-muted">{review.role}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* For Car Owners */}
      <section className="py-20">
        <div ref={section5.ref} className={`container transition-all duration-700 ${section5.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h2 className="mb-4 text-center text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'لملاك السيارات' : 'For Car Owners'}
          </h2>
          <p className="mb-10 text-center text-text-secondary">
            {lang === 'ar' ? 'سيارتك المتوقفة ممكن تصير مصدر دخل' : 'Your parked car can become a source of income'}
          </p>
          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Wallet,
                title: lang === 'ar' ? 'دخل إضافي' : 'Extra Income',
                desc: lang === 'ar' ? 'اكسب حتى 300 د.ك شهرياً من سيارتك المتوقفة' : 'Earn up to 300 KWD monthly from your parked car',
              },
              {
                icon: Shield,
                title: lang === 'ar' ? 'حماية كاملة' : 'Full Protection',
                desc: lang === 'ar' ? 'تأمين شامل وعقد واضح يحمي حقوقك كمالك' : 'Comprehensive insurance and clear contract to protect your rights',
              },
              {
                icon: Clock,
                title: lang === 'ar' ? 'تحكم كامل' : 'Full Control',
                desc: lang === 'ar' ? 'أنت تحدد السعر والتواريخ وشروط التأجير' : 'You set the price, dates, and rental terms',
              },
            ].map((item, i) => (
              <div key={i} className="rounded-2xl border border-dark-border bg-dark-card p-6 text-center transition-all duration-300 hover:-translate-y-1 hover:border-status-star/30">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-status-star/10 border border-status-star/20">
                  <item.icon className="h-7 w-7 text-status-star" />
                </div>
                <h3 className="mb-2 text-lg font-bold text-text-primary">{item.title}</h3>
                <p className="text-sm text-text-secondary">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section - Gold Gradient */}
      <section className="py-16">
        <div className="container">
          <div className="rounded-3xl bg-gradient-to-br from-[#FFB800] to-[#FF9500] px-8 py-12 text-center shadow-xl shadow-status-star/20 md:px-16">
            <h2 className="mb-4 text-3xl font-bold text-dark-bg">
              {lang === 'ar'
                ? 'عندك سيارة؟ حوّلها لمصدر دخل!'
                : 'Have a Car? Turn it into Income!'}
            </h2>
            <p className="mb-8 text-lg text-dark-bg/80">
              {lang === 'ar'
                ? 'سجّل سيارتك على سكة كار وابدأ بكسب المال من سيارتك المتوقفة'
                : 'List your car on Sikka Car and start earning from your parked car'}
            </p>
            <Link
              href="/list"
              className="inline-flex items-center gap-2 rounded-xl bg-dark-bg px-8 py-4 text-lg font-bold text-text-primary shadow-2xl transition-all hover:-translate-y-0.5 hover:bg-dark-card"
            >
              {t('listYourCar')}
              <Arrow className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-darker border-t border-dark-border py-16">
        <div className="container">
          <div className="mb-12 grid gap-12 md:grid-cols-3">
            {/* Left Column - Logo & Description */}
            <div>
              <div className="mb-4 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-dark-card border border-dark-border">
                  <Car className="h-4 w-4 text-status-star" />
                </div>
                <span className="text-lg font-bold text-text-primary">
                  Sikka <span className="text-status-star">Car</span>
                </span>
              </div>
              <p className="text-sm text-text-secondary">
                {lang === 'ar'
                  ? 'منصة كويتية موثوقة تربط ملاك السيارات بالمستأجرين بكل سهولة وأمان'
                  : 'A trusted Kuwaiti platform connecting car owners with renters — easy, secure, and seamless.'}
              </p>
            </div>

            {/* Middle Column - Quick Links */}
            <div>
              <h4 className="mb-4 font-bold text-text-primary">
                {lang === 'ar' ? 'الروابط السريعة' : 'Quick Links'}
              </h4>
              <ul className="space-y-2 text-sm text-text-secondary">
                <li>
                  <Link href="/browse" className="transition-colors hover:text-status-star">
                    {lang === 'ar' ? 'تصفح السيارات' : 'Browse Cars'}
                  </Link>
                </li>
                <li>
                  <Link href="/list" className="transition-colors hover:text-status-star">
                    {lang === 'ar' ? 'ضيف سيارتك' : 'List Your Car'}
                  </Link>
                </li>
                <li>
                  <Link href="/contact" className="transition-colors hover:text-status-star">
                    {lang === 'ar' ? 'تواصل معنا' : 'Contact Us'}
                  </Link>
                </li>
                <li>
                  <Link href="/faq" className="transition-colors hover:text-status-star">
                    {lang === 'ar' ? 'الأسئلة الشائعة' : 'FAQ'}
                  </Link>
                </li>
                <li>
                  <Link href="/terms" className="transition-colors hover:text-status-star">
                    {lang === 'ar' ? 'شروط الاستخدام' : 'Terms'}
                  </Link>
                </li>
                <li>
                  <Link href="/privacy" className="transition-colors hover:text-status-star">
                    {lang === 'ar' ? 'سياسة الخصوصية' : 'Privacy'}
                  </Link>
                </li>
              </ul>
            </div>

            {/* Right Column - Social & Contact */}
            <div>
              <h4 className="mb-4 font-bold text-text-primary">
                {lang === 'ar' ? 'تواصل معنا' : 'Connect With Us'}
              </h4>
              <div className="mb-4 flex gap-3">
                <a
                  href="https://instagram.com"
                  rel="noopener noreferrer"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-dark-card border border-dark-border transition-all hover:border-status-star/50 hover:bg-status-star/10"
                  aria-label="Instagram"
                >
                  <Instagram className="h-4 w-4 text-text-secondary" />
                </a>
                <a
                  href="https://twitter.com"
                  rel="noopener noreferrer"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-dark-card border border-dark-border transition-all hover:border-status-star/50 hover:bg-status-star/10"
                  aria-label="Twitter"
                >
                  <Twitter className="h-4 w-4 text-text-secondary" />
                </a>
              </div>
              <div className="space-y-2">
                <p className="flex items-center gap-2 text-xs text-text-muted">
                  <Phone className="h-3.5 w-3.5 text-status-star" />
                  <a href="tel:+96500000000" className="hover:text-status-star transition-colors">+965 0000 0000</a>
                </p>
                <p className="flex items-center gap-2 text-xs text-text-muted">
                  <Mail className="h-3.5 w-3.5 text-status-star" />
                  <a href="mailto:support@sikkacar.com" className="hover:text-status-star transition-colors">
                    support@sikkacar.com
                  </a>
                </p>
              </div>
            </div>
          </div>

          {/* Bottom - Copyright & Legal */}
          <div className="border-t border-dark-border pt-8">
            <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
              <p className="text-sm text-text-secondary">{t('copyright')}</p>
              <LegalLinks />
            </div>
          </div>
        </div>
      </footer>
    </main>
  )
}
