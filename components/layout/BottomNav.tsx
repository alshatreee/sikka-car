'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Home, Search, PlusCircle, LayoutDashboard, User } from 'lucide-react'
import { useAuth } from '@clerk/nextjs'

export default function BottomNav() {
  const pathname = usePathname()
  const { t } = useLanguage()
  const { isSignedIn } = useAuth()

  const links = [
    { href: '/', icon: Home, label: t('home') },
    { href: '/browse', icon: Search, label: t('browse') },
    ...(isSignedIn
      ? [
          { href: '/list', icon: PlusCircle, label: t('listCar') },
          { href: '/dashboard', icon: LayoutDashboard, label: t('dashboard') },
        ]
      : [{ href: '/sign-in', icon: User, label: t('signIn') }]),
  ]

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-dark-border bg-dark-bg shadow-lg md:hidden">
      <div className="flex items-center justify-around py-2">
        {links.map((link) => {
          const isActive = pathname === link.href
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex flex-col items-center gap-0.5 px-3 py-1 text-[10px] transition-colors ${
                isActive
                  ? 'text-status-star'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <link.icon
                className={`h-5 w-5 ${isActive ? 'text-status-star' : ''}`}
              />
              <span>{link.label}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
