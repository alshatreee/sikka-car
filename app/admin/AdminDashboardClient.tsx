'use client'

import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import {
  Users,
  Car,
  CalendarCheck,
  Clock,
  CheckCircle2,
  XCircle,
  DollarSign,
  TrendingUp,
  ArrowUpRight,
} from 'lucide-react'

interface Stats {
  totalUsers: number
  totalCars: number
  pendingCars: number
  approvedCars: number
  rejectedCars: number
  totalBookings: number
  activeBookings: number
  totalRevenue: number
}

export default function AdminDashboardClient({ stats }: { stats: Stats }) {
  const { t, lang } = useLanguage()

  const cards = [
    {
      label: t('adminTotalUsers'),
      value: stats.totalUsers,
      icon: Users,
      color: 'text-blue-400',
      iconBg: 'bg-blue-400/10 border-blue-400/20',
      border: 'border-blue-400/20',
      href: '/admin/users',
    },
    {
      label: t('adminTotalCars'),
      value: stats.totalCars,
      icon: Car,
      color: 'text-status-star',
      iconBg: 'bg-status-star/10 border-status-star/20',
      border: 'border-status-star/20',
      href: '/admin/cars',
    },
    {
      label: t('adminPendingCars'),
      value: stats.pendingCars,
      icon: Clock,
      color: 'text-status-warning',
      iconBg: 'bg-status-warning/10 border-status-warning/20',
      border: 'border-status-warning/20',
      href: '/admin/cars?status=PENDING',
    },
    {
      label: t('adminApprovedCars'),
      value: stats.approvedCars,
      icon: CheckCircle2,
      color: 'text-status-success',
      iconBg: 'bg-status-success/10 border-status-success/20',
      border: 'border-status-success/20',
      href: '/admin/cars?status=APPROVED',
    },
    {
      label: t('adminRejectedCars'),
      value: stats.rejectedCars,
      icon: XCircle,
      color: 'text-red-400',
      iconBg: 'bg-red-400/10 border-red-400/20',
      border: 'border-red-400/20',
      href: '/admin/cars?status=REJECTED',
    },
    {
      label: t('adminTotalBookings'),
      value: stats.totalBookings,
      icon: CalendarCheck,
      color: 'text-purple-400',
      iconBg: 'bg-purple-400/10 border-purple-400/20',
      border: 'border-purple-400/20',
      href: '/admin/bookings',
    },
    {
      label: t('adminActiveBookings'),
      value: stats.activeBookings,
      icon: TrendingUp,
      color: 'text-emerald-400',
      iconBg: 'bg-emerald-400/10 border-emerald-400/20',
      border: 'border-emerald-400/20',
      href: '/admin/bookings',
    },
    {
      label: t('adminTotalRevenue'),
      value: `${stats.totalRevenue.toFixed(1)} ${t('kwd')}`,
      icon: DollarSign,
      color: 'text-status-star',
      iconBg: 'bg-status-star/10 border-status-star/20',
      border: 'border-status-star/20',
      href: '/admin/bookings',
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">
          {t('adminDashboard')}
        </h1>
        <p className="mt-1 text-text-secondary">
          {lang === 'ar' ? 'إدارة شاملة لمنصة سكة كار' : 'Full platform management for Sikka Car'}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className={`group rounded-2xl border ${card.border} bg-dark-card p-5 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:border-status-star/30`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full border ${card.iconBg}`}>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
              <ArrowUpRight className="h-4 w-4 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
            </div>
            <p className={`text-2xl font-bold ${card.color}`}>
              {card.value}
            </p>
            <p className="mt-1 text-sm text-text-secondary">{card.label}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
