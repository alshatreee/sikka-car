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
  const { t } = useLanguage()

  const cards = [
    {
      label: t('adminTotalUsers'),
      value: stats.totalUsers,
      icon: Users,
      color: 'text-blue-400',
      bg: 'bg-blue-400/10',
      border: 'border-blue-400/20',
      href: '/admin/users',
    },
    {
      label: t('adminTotalCars'),
      value: stats.totalCars,
      icon: Car,
      color: 'text-status-star',
      bg: 'bg-status-star/10',
      border: 'border-status-star/20',
      href: '/admin/cars',
    },
    {
      label: t('adminPendingCars'),
      value: stats.pendingCars,
      icon: Clock,
      color: 'text-status-warning',
      bg: 'bg-status-warning/10',
      border: 'border-status-warning/20',
      href: '/admin/cars?status=PENDING',
    },
    {
      label: t('adminApprovedCars'),
      value: stats.approvedCars,
      icon: CheckCircle2,
      color: 'text-status-success',
      bg: 'bg-status-success/10',
      border: 'border-status-success/20',
      href: '/admin/cars?status=APPROVED',
    },
    {
      label: t('adminRejectedCars'),
      value: stats.rejectedCars,
      icon: XCircle,
      color: 'text-red-400',
      bg: 'bg-red-400/10',
      border: 'border-red-400/20',
      href: '/admin/cars?status=REJECTED',
    },
    {
      label: t('adminTotalBookings'),
      value: stats.totalBookings,
      icon: CalendarCheck,
      color: 'text-purple-400',
      bg: 'bg-purple-400/10',
      border: 'border-purple-400/20',
      href: '/admin/bookings',
    },
    {
      label: t('adminActiveBookings'),
      value: stats.activeBookings,
      icon: TrendingUp,
      color: 'text-emerald-400',
      bg: 'bg-emerald-400/10',
      border: 'border-emerald-400/20',
      href: '/admin/bookings',
    },
    {
      label: t('adminTotalRevenue'),
      value: `${stats.totalRevenue.toFixed(1)} ${t('kwd')}`,
      icon: DollarSign,
      color: 'text-status-star',
      bg: 'bg-status-star/10',
      border: 'border-status-star/20',
      href: '/admin/bookings',
    },
  ]

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-text-primary">
        {t('adminDashboard')}
      </h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className={`rounded-2xl border ${card.border} ${card.bg} p-5 transition-all hover:-translate-y-0.5 hover:shadow-lg`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-secondary">{card.label}</p>
                <p className={`mt-1 text-2xl font-bold ${card.color}`}>
                  {card.value}
                </p>
              </div>
              <card.icon className={`h-8 w-8 ${card.color} opacity-60`} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
