'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { updateUserRole } from '@/actions/adminActions'
import { useState, useTransition } from 'react'
import {
  Users,
  Shield,
  User,
  Car,
  CalendarCheck,
  Mail,
  Phone,
} from 'lucide-react'

interface AdminUser {
  id: string
  email: string
  fullName?: string | null
  phone?: string | null
  role: string
  createdAt: string
  _count: { cars: number; bookings: number }
}

export default function AdminUsersClient({
  users: initialUsers,
}: {
  users: AdminUser[]
}) {
  const { t, lang } = useLanguage()
  const [users, setUsers] = useState(initialUsers)
  const [isPending, startTransition] = useTransition()

  const handleRoleChange = (userId: string, newRole: 'USER' | 'ADMIN') => {
    startTransition(async () => {
      await updateUserRole(userId, newRole)
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      )
    })
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(lang === 'ar' ? 'ar-KW' : 'en-KW')
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-text-primary">
        {t('adminUsers')}
      </h1>

      <p className="mb-4 text-sm text-text-secondary">
        {users.length} {lang === 'ar' ? 'مستخدم' : 'users'}
      </p>

      <div className="space-y-3">
        {users.map((user) => (
          <div
            key={user.id}
            className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-2xl border border-dark-border bg-dark-card p-4"
          >
            {/* Avatar */}
            <div className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full ${
              user.role === 'ADMIN'
                ? 'bg-status-star/10 border border-status-star/20'
                : 'bg-dark-surface border border-dark-border'
            }`}>
              {user.role === 'ADMIN' ? (
                <Shield className="h-5 w-5 text-status-star" />
              ) : (
                <User className="h-5 w-5 text-text-secondary" />
              )}
            </div>

            {/* Info */}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-text-primary">
                  {user.fullName || (lang === 'ar' ? 'بدون اسم' : 'No name')}
                </h3>
                {user.role === 'ADMIN' && (
                  <span className="rounded-full bg-status-star/10 border border-status-star/20 px-2 py-0.5 text-[10px] font-medium text-status-star">
                    Admin
                  </span>
                )}
              </div>
              <div className="mt-1 flex flex-wrap gap-3 text-sm text-text-secondary">
                <span className="flex items-center gap-1">
                  <Mail className="h-3.5 w-3.5" />
                  {user.email}
                </span>
                {user.phone && (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3.5 w-3.5" />
                    {user.phone}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Car className="h-3.5 w-3.5" />
                  {user._count.cars} {lang === 'ar' ? 'سيارة' : 'cars'}
                </span>
                <span className="flex items-center gap-1">
                  <CalendarCheck className="h-3.5 w-3.5" />
                  {user._count.bookings} {lang === 'ar' ? 'حجز' : 'bookings'}
                </span>
              </div>
              <p className="mt-1 text-xs text-text-muted">
                {lang === 'ar' ? 'انضم' : 'Joined'} {formatDate(user.createdAt)}
              </p>
            </div>

            {/* Role Toggle */}
            <button
              onClick={() =>
                handleRoleChange(
                  user.id,
                  user.role === 'ADMIN' ? 'USER' : 'ADMIN'
                )
              }
              disabled={isPending}
              className={`flex-shrink-0 rounded-xl px-4 py-2 text-xs font-medium transition-colors disabled:opacity-50 ${
                user.role === 'ADMIN'
                  ? 'bg-red-400/10 border border-red-400/20 text-red-400 hover:bg-red-400/20'
                  : 'bg-status-star/10 border border-status-star/20 text-status-star hover:bg-status-star/20'
              }`}
            >
              {user.role === 'ADMIN'
                ? lang === 'ar' ? 'إزالة الأدمن' : 'Remove Admin'
                : lang === 'ar' ? 'ترقية لأدمن' : 'Make Admin'}
            </button>
          </div>
        ))}

        {users.length === 0 && (
          <div className="rounded-2xl border border-dark-border bg-dark-card p-12 text-center">
            <Users className="mx-auto mb-3 h-12 w-12 text-text-muted" />
            <p className="text-text-secondary">{t('noResults')}</p>
          </div>
        )}
      </div>
    </div>
  )
}
