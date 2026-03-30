import type { Metadata } from 'next'
import { ClerkProvider } from '@clerk/nextjs'
import { arSA } from '@clerk/localizations'
import './globals.css'
import ClientLayout from './ClientLayout'
import GoogleAnalytics from '@/components/shared/GoogleAnalytics'

export const metadata: Metadata = {
  title: {
    default: 'سكة كار | Sikka Car - تأجير سيارات بين الأفراد في الكويت',
    template: '%s | سكة كار - Sikka Car',
  },
  description:
    'أكبر منصة كويتية لتأجير السيارات بين الأفراد. استأجر سيارة بسعر مناسب أو أضف سيارتك واكسب دخل إضافي. دفع آمن عبر K-Net و Visa.',
  keywords: [
    'تأجير سيارات الكويت',
    'سكة كار',
    'تأجير سيارات بين الأفراد',
    'إيجار سيارات',
    'car rental Kuwait',
    'peer to peer car rental',
    'Sikka Car',
    'rent a car Kuwait',
    'كراج سيارات',
    'سيارات للإيجار',
  ],
  openGraph: {
    title: 'سكة كار | Sikka Car',
    description: 'أكبر منصة كويتية لتأجير السيارات بين الأفراد — سهل، آمن، وموثوق',
    type: 'website',
    locale: 'ar_KW',
    alternateLocale: 'en_US',
    siteName: 'Sikka Car - سكة كار',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'سكة كار | Sikka Car',
    description: 'أكبر منصة كويتية لتأجير السيارات بين الأفراد',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  alternates: {
    canonical: 'https://sikkacar.com',
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
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify({
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "Sikka Car",
                "alternateName": "سكة كار",
                "url": "https://sikkacar.com",
                "logo": "https://sikkacar.com/icon.svg",
                "description": "منصة كويتية موثوقة لتأجير السيارات بين الأفراد",
                "areaServed": {
                  "@type": "Country",
                  "name": "Kuwait"
                },
                "contactPoint": {
                  "@type": "ContactPoint",
                  "email": "support@sikkacar.com",
                  "contactType": "customer service",
                  "availableLanguage": ["Arabic", "English"]
                },
                "sameAs": []
              })
            }}
          />
        </head>
        <body className="font-arabic">
          <GoogleAnalytics />
          <ClientLayout>{children}</ClientLayout>
        </body>
      </html>
    </ClerkProvider>
  )
}
