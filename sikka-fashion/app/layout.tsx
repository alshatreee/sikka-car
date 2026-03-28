import type { Metadata } from "next";
import "./globals.css";
import ClientLayout from "./ClientLayout";

export const metadata: Metadata = {
  title: {
    default: "خزانة | Khizana — منصة تأجير وبيع الأزياء النسائية في الكويت",
    template: "%s | خزانة Khizana",
  },
  description:
    "أجّري أو اشتري أزياء المصممين للمناسبات في الكويت. بدل نسائية، فساتين سهرة، عبايات مصممة بأسعار ذكية. Rent or buy designer women's fashion in Kuwait.",
  keywords: [
    "تأجير فساتين الكويت",
    "بيع أزياء مصممين",
    "فساتين سهرة للإيجار",
    "عبايات مصممة",
    "خزانة",
    "Khizana",
    "Kuwait fashion rental",
    "designer dress rental Kuwait",
    "women fashion marketplace Kuwait",
    "rent evening gown Kuwait",
  ],
  openGraph: {
    title: "خزانة | Khizana — تأجير وبيع الأزياء النسائية",
    description:
      "أجّري أو اشتري أزياء المصممين للمناسبات في الكويت — بأسعار ذكية",
    type: "website",
    locale: "ar_KW",
    alternateLocale: "en_US",
    siteName: "خزانة Khizana",
  },
  twitter: {
    card: "summary_large_image",
    title: "خزانة | Khizana",
    description: "منصة تأجير وبيع الأزياء النسائية في الكويت",
  },
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    languages: {
      ar: "/",
      en: "/",
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-arabic antialiased">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
