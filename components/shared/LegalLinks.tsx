'use client'

import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'

export default function LegalLinks() {
  const { lang } = useLanguage()

  return (
    <div className="flex flex-wrap gap-4 text-sm text-text-muted">
      <Link
        href="/terms"
        className="transition-colors hover:text-status-star"
      >
        {lang === 'ar' ? 'شروط الاستخدام' : 'Terms of Service'}
      </Link>
      <span className="text-dark-border">|</span>
      <Link
        href="/privacy"
        className="transition-colors hover:text-status-star"
      >
        {lang === 'ar' ? 'سياسة الخصوصية' : 'Privacy Policy'}
      </Link>
    </div>
  )
}
