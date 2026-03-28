import type { Metadata } from 'next'
import { ClerkProvider } from '@clerk/nextjs'
import { arSA } from '@clerk/localizations'
import './globals.css'
import ClientLayout from './ClientLayout'

export const metadata: Metadata = {
  title: 'Sikka Car | سكة كار - تأجير سيارات في الكويت',
  description:
    'أكبر منصة لتأجير السيارات بين الأفراد في الكويت. استأجر سيارتك المثالية أو أضف سيارتك للإيجار.',
  keywords: [
    'تأجير سيارات',
    'الكويت',
    'سكة كار',
    'car rental',
    'Kuwait',
    'Sikka Car',
  ],
  openGraph: {
    title: 'Sikka Car | سكة كار',
    description: 'أكبر منصة لتأجير السيارات بين الأفراد في الكويت',
    type: 'website',
    locale: 'ar_KW',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider localization={arSA as any}>
      <html lang="ar" dir="rtl" suppressHydrationWarning>
        <head>
          <link
            href="https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@300;400;500;600;700;800&display=swap"
            rel="stylesheet"
          />
        </head>
        <body className="font-arabic">
          <ClientLayout>{children}</ClientLayout>
        </body>
      </html>
    </ClerkProvider>
  )
}
