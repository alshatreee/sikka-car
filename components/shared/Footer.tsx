'use client'

import Link from 'next/link'
import { Car, Instagram, Twitter, Phone, Mail } from 'lucide-react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import LegalLinks from '@/components/shared/LegalLinks'

export default function Footer() {
  const { t, lang } = useLanguage()

  return (
    <footer className="bg-darker border-t border-dark-border py-16">
      <div className="container">
        <div className="mb-12 grid gap-12 md:grid-cols-3">
          {/* Left Column - Logo & Description */}
          <div>
            <div className="mb-4 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-dark-card border border-dark-border">
                <Car className="h-4 w-4 text-status-star" />
              </div>
              <span className="text-lg font-bold text-text-primary">
                Sikka <span className="text-status-star">Car</span>
              </span>
            </div>
            <p className="text-sm text-text-secondary">
              {lang === 'ar'
                ? 'منصة كويتية موثوقة تربط ملاك السيارات بالمستأجرين بكل سهولة وأمان'
                : 'A trusted Kuwaiti platform connecting car owners with renters — easy, secure, and seamless.'}
            </p>
          </div>

          {/* Middle Column - Quick Links */}
          <div>
            <h4 className="mb-4 font-bold text-text-primary">
              {lang === 'ar' ? 'الروابط السريعة' : 'Quick Links'}
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <Link href="/browse" className="transition-colors hover:text-status-star">
                  {lang === 'ar' ? 'تصفح السيارات' : 'Browse Cars'}
                </Link>
              </li>
              <li>
                <Link href="/list" className="transition-colors hover:text-status-star">
                  {lang === 'ar' ? 'ضيف سيارتك' : 'List Your Car'}
                </Link>
              </li>
              <li>
                <Link href="/contact" className="transition-colors hover:text-status-star">
                  {lang === 'ar' ? 'تواصل معنا' : 'Contact Us'}
                </Link>
              </li>
              <li>
                <Link href="/faq" className="transition-colors hover:text-status-star">
                  {lang === 'ar' ? 'الأسئلة الشائعة' : 'FAQ'}
                </Link>
              </li>
              <li>
                <Link href="/terms" className="transition-colors hover:text-status-star">
                  {lang === 'ar' ? 'شروط الاستخدام' : 'Terms'}
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="transition-colors hover:text-status-star">
                  {lang === 'ar' ? 'سياسة الخصوصية' : 'Privacy'}
                </Link>
              </li>
            </ul>
          </div>

          {/* Right Column - Social & Contact */}
          <div>
            <h4 className="mb-4 font-bold text-text-primary">
              {lang === 'ar' ? 'تواصل معنا' : 'Connect With Us'}
            </h4>
            <div className="mb-4 flex gap-3">
              <a
                href="https://instagram.com"
                rel="noopener noreferrer"
                className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-dark-card border border-dark-border transition-all hover:border-status-star/50 hover:bg-status-star/10"
                aria-label="Instagram"
              >
                <Instagram className="h-4 w-4 text-text-secondary" />
              </a>
              <a
                href="https://twitter.com"
                rel="noopener noreferrer"
                className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-dark-card border border-dark-border transition-all hover:border-status-star/50 hover:bg-status-star/10"
                aria-label="Twitter"
              >
                <Twitter className="h-4 w-4 text-text-secondary" />
              </a>
            </div>
            <div className="space-y-2">
              <p className="flex items-center gap-2 text-xs text-text-muted">
                <Phone className="h-3.5 w-3.5 text-status-star" />
                <a href="tel:+96500000000" className="hover:text-status-star transition-colors">+965 0000 0000</a>
              </p>
              <p className="flex items-center gap-2 text-xs text-text-muted">
                <Mail className="h-3.5 w-3.5 text-status-star" />
                <a href="mailto:support@sikkacar.com" className="hover:text-status-star transition-colors">
                  support@sikkacar.com
                </a>
              </p>
            </div>
          </div>
        </div>

        {/* Bottom - Copyright & Legal */}
        <div className="border-t border-dark-border pt-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <p className="text-sm text-text-secondary">{t('copyright')}</p>
            <LegalLinks />
          </div>
        </div>
      </div>
    </footer>
  )
}
