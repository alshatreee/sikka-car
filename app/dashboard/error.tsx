'use client'

import { useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const { lang } = useLanguage()

  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="mb-6 flex justify-center">
          <div className="rounded-full bg-dark-card border border-dark-border p-6">
            <AlertTriangle className="h-12 w-12 text-status-star" />
          </div>
        </div>
        <h1 className="mb-3 text-3xl font-bold text-text-primary">
          {lang === 'ar' ? 'حدث خطأ' : 'Something went wrong'}
        </h1>
        <p className="mb-8 text-text-secondary">
          {lang === 'ar'
            ? 'عذراً، حدث خطأ أثناء تحميل لوحة التحكم. يرجى المحاولة مرة أخرى.'
            : 'Sorry, an error occurred while loading the dashboard. Please try again.'}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            onClick={() => reset()}
            className="rounded-xl border border-text-primary bg-transparent px-8 py-3 font-medium text-text-primary transition-all hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'حاول مرة أخرى' : 'Try Again'}
          </button>
          <Link
            href="/"
            className="rounded-xl border border-dark-border-light bg-transparent px-8 py-3 font-medium text-text-secondary transition-all hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'الرئيسية' : 'Home'}
          </Link>
        </div>
      </div>
    </main>
  )
}
