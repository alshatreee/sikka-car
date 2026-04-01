'use client'

import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { SignedIn, SignedOut, UserButton } from '@clerk/nextjs'
import { Car, Globe, Menu, X, Shield, MessageCircle, BookOpen } from 'lucide-react'
import { useState, useEffect } from 'react'

export default function Header() {
  const { t, toggleLanguage, lang } = useLanguage()
  const [menuOpen, setMenuOpen] = useState(false)
  const [isAdminUser, setIsAdminUser] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    fetch('/api/me')
      .then((r) => r.json())
      .then((data) => setIsAdminUser(data.role === 'ADMIN'))
      .catch(() => {})

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
  }, [])

  return (
    <header className="sticky top-0 z-50 border-b border-dark-border bg-dark-bg backdrop-blur-md">
      <div className="container mx-auto flex items-center justify-between px-4 py-3">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-dark-card border border-dark-border">
            <Car className="h-5 w-5 text-status-star" />
          </div>
          <span className="text-xl font-bold text-text-primary">
            Sikka <span className="text-status-star">Car</span>
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden items-center gap-6 md:flex">
          <Link
            href="/browse"
            className="text-sm text-text-secondary transition-colors hover:text-text-primary"
          >
            {t('browse')}
          </Link>
          <SignedIn>
            <Link
              href="/list"
              className="text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              {t('listCar')}
            </Link>
            <Link
              href="/dashboard"
              className="text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              {t('dashboard')}
            </Link>
            <Link
              href="/profile"
              className="text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              {lang === 'ar' ? 'ملفي' : 'Profile'}
            </Link>
            <Link
              href="/messages"
              className="relative flex items-center gap-1 text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              <MessageCircle className="h-4 w-4" />
              {t('messages')}
              {unreadCount > 0 && (
                <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-status-star text-dark-bg text-xs font-bold absolute -top-2 -right-2">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </Link>
            <Link
              href="/kazima"
              className="flex items-center gap-1 text-sm text-text-secondary transition-colors hover:text-status-star"
            >
              <BookOpen className="h-4 w-4" />
              {lang === 'ar' ? 'كاظمة AI' : 'Kazima AI'}
            </Link>
            {isAdminUser && (
              <Link
                href="/admin"
                className="flex items-center gap-1 text-sm text-status-star transition-colors hover:text-status-star/80"
              >
                <Shield className="h-3.5 w-3.5" />
                {t('adminPanel')}
              </Link>
            )}
          </SignedIn>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={toggleLanguage}
            className="flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
          >
            <Globe className="h-3.5 w-3.5" />
            {lang === 'ar' ? 'EN' : 'عربي'}
          </button>

          <SignedOut>
            <Link
              href="/sign-in"
              className="hidden rounded-lg border border-text-primary bg-transparent px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-dark-surface md:block"
            >
              {t('signIn')}
            </Link>
          </SignedOut>

          <SignedIn>
            <UserButton
              afterSignOutUrl="/"
              appearance={{
                elements: {
                  avatarBox: 'h-8 w-8',
                },
              }}
            />
          </SignedIn>

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="text-text-secondary md:hidden"
          >
            {menuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {menuOpen && (
        <div className="border-t border-dark-border bg-dark-bg px-4 py-4 md:hidden">
          <nav className="flex flex-col gap-3">
            <Link
              href="/browse"
              onClick={() => setMenuOpen(false)}
              className="rounded-lg px-3 py-2 text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
            >
              {t('browse')}
            </Link>
            <SignedIn>
              <Link
                href="/list"
                onClick={() => setMenuOpen(false)}
                className="rounded-lg px-3 py-2 text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
              >
                {t('listCar')}
              </Link>
              <Link
                href="/dashboard"
                onClick={() => setMenuOpen(false)}
                className="rounded-lg px-3 py-2 text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
              >
                {t('dashboard')}
              </Link>
              <Link
                href="/profile"
                onClick={() => setMenuOpen(false)}
                className="rounded-lg px-3 py-2 text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
              >
                {lang === 'ar' ? 'ملفي' : 'Profile'}
              </Link>
              <Link
                href="/messages"
                onClick={() => setMenuOpen(false)}
                className="relative flex items-center gap-2 rounded-lg px-3 py-2 text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
              >
                <MessageCircle className="h-4 w-4" />
                {t('messages')}
                {unreadCount > 0 && (
                  <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-status-star text-dark-bg text-xs font-bold">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </Link>
              <Link
                href="/kazima"
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-text-secondary transition-colors hover:bg-dark-surface hover:text-status-star"
              >
                <BookOpen className="h-4 w-4" />
                {lang === 'ar' ? 'كاظمة AI' : 'Kazima AI'}
              </Link>
              {isAdminUser && (
                <Link
                  href="/admin"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-status-star transition-colors hover:bg-dark-surface"
                >
                  <Shield className="h-4 w-4" />
                  {t('adminPanel')}
                </Link>
              )}
            </SignedIn>
            <SignedOut>
              <Link
                href="/sign-in"
                onClick={() => setMenuOpen(false)}
                className="rounded-lg border border-text-primary bg-transparent px-3 py-2 text-center text-text-primary"
              >
                {t('signIn')}
              </Link>
            </SignedOut>
          </nav>
        </div>
      )}
    </header>
  )
}
