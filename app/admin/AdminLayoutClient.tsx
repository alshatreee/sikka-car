'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useLanguage } from '@/components/shared/LanguageProvider'
import {
  LayoutDashboard,
  Car,
  CalendarCheck,
  Users,
  ArrowRight,
} from 'lucide-react'

export default function AdminLayoutClient({
  children,
}: {
  children: React.ReactNode
}) {
  const { t } = useLanguage()
  const pathname = usePathname()

  const links = [
    { href: '/admin', icon: LayoutDashboard, label: t('adminDashboard') },
    { href: '/admin/cars', icon: Car, label: t('adminCars') },
    { href: '/admin/bookings', icon: CalendarCheck, label: t('adminBookings') },
    { href: '/admin/users', icon: Users, label: t('adminUsers') },
  ]

  return (
    <div className="container py-8 pb-24 md:pb-8">
      {/* Back link */}
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowRight className="h-4 w-4 rotate-180" />
        {t('backToSite')}
      </Link>

      {/* Admin Nav Tabs */}
      <div className="mb-8 flex gap-2 overflow-x-auto pb-2">
        {links.map((link) => {
          const isActive =
            link.href === '/admin'
              ? pathname === '/admin'
              : pathname.startsWith(link.href)
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                isActive
                  ? 'bg-status-star text-dark-bg'
                  : 'border border-dark-border bg-dark-card text-text-secondary hover:bg-dark-surface hover:text-text-primary'
              }`}
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          )
        })}
      </div>

      {children}
    </div>
  )
}
