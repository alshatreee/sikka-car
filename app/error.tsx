'use client'

import { useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useLanguage } from '@/components/shared/LanguageProvider'

export default function Error({
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
    <main className="flex min-h-[80vh] items-center justify-center px-4">
      <div className="text-center">
        <div className="mb-6 flex justify-center">
          <div className="rounded-full bg-dark-card border border-dark-border p-6">
            <AlertTriangle className="h-12 w-12 text-status-star" />
          </div>
        </div>
        <h1 className="mb-3 text-3xl font-bold text-text-primary">
          {lang === 'ar' ? 'حدث خطأ' : 'Something went wrong'}
        </h1>
        <p className="mb-8 max-w-md text-text-secondary">
          {lang === 'ar'
            ? 'عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو العودة إلى الصفحة الرئيسية.'
            : 'Sorry, an unexpected error occurred. Please try again or return to the homepage.'}
        </p>
        <button
          onClick={() => reset()}
          className="rounded-xl border border-text-primary bg-transparent px-8 py-3 font-medium text-text-primary transition-all hover:bg-dark-surface"
        >
          {lang === 'ar' ? 'حاول مرة أخرى' : 'Try again'}
        </button>
      </div>
    </main>
  )
}
