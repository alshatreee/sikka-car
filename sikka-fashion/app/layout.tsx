import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { arSA } from "@clerk/localizations";
import "./globals.css";
import ClientLayout from "./ClientLayout";

export const metadata: Metadata = {
  title: "خزانة | Khizana — منصة تأجير وبيع الأزياء النسائية في الكويت",
  description:
    "أجّري أو اشتري أزياء المصممين للمناسبات في الكويت. بدل نسائية، فساتين سهرة، عبايات مصممة بأسعار ذكية.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider localization={arSA as any}>
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
    </ClerkProvider>
  );
}
