'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Home, Search, PlusCircle, LayoutDashboard, User, MessageCircle, BookOpen } from 'lucide-react'
import { useAuth } from '@clerk/nextjs'
import { useState, useEffect } from 'react'

export default function BottomNav() {
  const pathname = usePathname()
  const { t, lang } = useLanguage()
  const { isSignedIn } = useAuth()
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!isSignedIn) return

    // Load unread message count
    const loadUnreadCount = async () => {
      try {
        const response = await fetch('/api/messages/unread')
        const data = await response.json()
        setUnreadCount(data.count || 0)
      } catch (error) {
        console.error('Failed to load unread count:', error)
      }
    }

    loadUnreadCount()
    const interval = setInterval(loadUnreadCount, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [isSignedIn])

  const links = [
    { href: '/', icon: Home, label: t('home') },
    { href: '/browse', icon: Search, label: t('browse') },
    { href: '/kazima', icon: BookOpen, label: lang === 'ar' ? 'كاظمة' : 'Kazima' },
    ...(isSignedIn
      ? [
          { href: '/list', icon: PlusCircle, label: t('listCar') },
          { href: '/dashboard', icon: LayoutDashboard, label: t('dashboard') },
        ]
      : [{ href: '/sign-in', icon: User, label: t('signIn') }]),
  ]

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-dark-border bg-dark-bg shadow-lg md:hidden">
      <div className="flex items-center justify-around py-1.5">
        {links.map((link) => {
          const isActive = pathname === link.href
          const badge = 'badge' in link ? link.badge : 0
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`relative flex min-h-[44px] min-w-[44px] flex-col items-center justify-center gap-0.5 px-3 py-1.5 text-xs transition-colors ${
                isActive
                  ? 'text-status-star'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <link.icon
                className={`h-6 w-6 ${isActive ? 'text-status-star' : ''}`}
              />
              <span>{link.label}</span>
              {badge && badge > 0 && (
                <span className="absolute -top-1 -right-1 inline-flex items-center justify-center h-5 w-5 rounded-full bg-status-star text-dark-bg text-xs font-bold">
                  {badge > 9 ? '9+' : badge}
                </span>
              )}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
