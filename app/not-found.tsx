'use client'

import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Home, Search } from 'lucide-react'

export default function NotFound() {
  const { lang } = useLanguage()

  return (
    <main className="flex min-h-[80vh] items-center justify-center px-4">
      <div className="text-center">
        <div className="mb-4 text-8xl font-black text-text-secondary">404</div>
        <h1 className="mb-3 text-2xl font-bold text-text-primary">
          {lang === 'ar' ? 'الصفحة غير موجودة' : 'Page Not Found'}
        </h1>
        <p className="mb-8 text-text-secondary">
          {lang === 'ar'
            ? 'الصفحة التي تبحث عنها غير موجودة أو تم نقلها'
            : "The page you're looking for doesn't exist or has been moved"}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link href="/" className="btn-primary flex items-center justify-center gap-2">
            <Home className="h-4 w-4" />
            {lang === 'ar' ? 'الرئيسية' : 'Home'}
          </Link>
          <Link
            href="/browse"
            className="btn-secondary flex items-center justify-center gap-2"
          >
            <Search className="h-4 w-4" />
            {lang === 'ar' ? 'تصفح السيارات' : 'Browse Cars'}
          </Link>
        </div>
      </div>
    </main>
  )
}
