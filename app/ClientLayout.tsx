'use client'

import { LanguageProvider } from '@/components/shared/LanguageProvider'
import { ToastProvider } from '@/components/shared/Toast'
import Header from '@/components/layout/Header'
import BottomNav from '@/components/layout/BottomNav'

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <LanguageProvider>
      <ToastProvider>
        <div className="flex min-h-screen flex-col">
          <Header />
          <div className="flex-1">{children}</div>
          <BottomNav />
        </div>
      </ToastProvider>
    </LanguageProvider>
  )
}
