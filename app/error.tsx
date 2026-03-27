'use client'

import { useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <head>
        <title>حدث خطأ</title>
      </head>
      <body className="font-arabic bg-dark-bg text-text-primary antialiased">
        <main className="flex min-h-screen items-center justify-center px-4">
          <div className="text-center">
            <div className="mb-6 flex justify-center">
              <div className="rounded-full bg-dark-card border border-dark-border p-6">
                <AlertTriangle className="h-12 w-12 text-status-star" />
              </div>
            </div>
            <h1 className="mb-3 text-3xl font-bold text-text-primary">
              حدث خطأ
            </h1>
            <p className="mb-8 max-w-md text-text-secondary">
              عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو العودة إلى الصفحة الرئيسية.
            </p>
            <button
              onClick={() => reset()}
              className="rounded-xl border border-text-primary bg-transparent px-8 py-3 font-medium text-text-primary transition-all hover:bg-dark-surface"
            >
              حاول مرة أخرى
            </button>
          </div>
        </main>
      </body>
    </html>
  )
}
