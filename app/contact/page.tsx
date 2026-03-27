'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { Mail, Phone, MapPin, Instagram, Twitter, Send } from 'lucide-react'
import { useState } from 'react'

export default function ContactPage() {
  const { lang } = useLanguage()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    // For now, open mailto link with the form data
    const subject = encodeURIComponent(
      lang === 'ar' ? 'رسالة من موقع سكة كار' : 'Message from Sikka Car'
    )
    const body = encodeURIComponent(
      `${lang === 'ar' ? 'الاسم' : 'Name'}: ${name}\n${lang === 'ar' ? 'البريد' : 'Email'}: ${email}\n\n${message}`
    )
    window.open(`mailto:support@sikkacar.com?subject=${subject}&body=${body}`)
    setSent(true)
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 text-center">
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'تواصل معنا' : 'Contact Us'}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar'
              ? 'عندك سؤال أو اقتراح؟ نحب نسمع منك!'
              : 'Have a question or suggestion? We\'d love to hear from you!'}
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-2">
          {/* Contact Info */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
              <h2 className="mb-4 text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'معلومات التواصل' : 'Contact Info'}
              </h2>
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-status-star/10 border border-status-star/20">
                    <Mail className="h-4 w-4 text-status-star" />
                  </div>
                  <div>
                    <p className="text-xs text-text-muted">
                      {lang === 'ar' ? 'البريد الإلكتروني' : 'Email'}
                    </p>
                    <a href="mailto:support@sikkacar.com" className="text-sm text-text-primary hover:text-status-star">
                      support@sikkacar.com
                    </a>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-status-star/10 border border-status-star/20">
                    <Phone className="h-4 w-4 text-status-star" />
                  </div>
                  <div>
                    <p className="text-xs text-text-muted">
                      {lang === 'ar' ? 'الهاتف' : 'Phone'}
                    </p>
                    <a href="tel:+96512345678" className="text-sm text-text-primary hover:text-status-star" dir="ltr">
                      +965 1234 5678
                    </a>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-status-star/10 border border-status-star/20">
                    <MapPin className="h-4 w-4 text-status-star" />
                  </div>
                  <div>
                    <p className="text-xs text-text-muted">
                      {lang === 'ar' ? 'الموقع' : 'Location'}
                    </p>
                    <p className="text-sm text-text-primary">
                      {lang === 'ar' ? 'الكويت' : 'Kuwait'}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Social Media */}
            <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
              <h2 className="mb-4 text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'تابعنا' : 'Follow Us'}
              </h2>
              <div className="flex gap-3">
                <a
                  href="https://instagram.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-12 w-12 items-center justify-center rounded-xl bg-dark-surface border border-dark-border transition-all hover:border-status-star/50 hover:bg-dark-border"
                >
                  <Instagram className="h-5 w-5 text-text-secondary" />
                </a>
                <a
                  href="https://twitter.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-12 w-12 items-center justify-center rounded-xl bg-dark-surface border border-dark-border transition-all hover:border-status-star/50 hover:bg-dark-border"
                >
                  <Twitter className="h-5 w-5 text-text-secondary" />
                </a>
              </div>
            </div>

            {/* Working Hours */}
            <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
              <h2 className="mb-4 text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'ساعات العمل' : 'Working Hours'}
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-secondary">
                    {lang === 'ar' ? 'السبت - الخميس' : 'Sat - Thu'}
                  </span>
                  <span className="text-text-primary" dir="ltr">9:00 AM - 9:00 PM</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">
                    {lang === 'ar' ? 'الجمعة' : 'Friday'}
                  </span>
                  <span className="text-text-primary" dir="ltr">2:00 PM - 9:00 PM</span>
                </div>
              </div>
            </div>
          </div>

          {/* Contact Form */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'أرسل لنا رسالة' : 'Send Us a Message'}
            </h2>

            {sent ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10 border border-green-500/20">
                  <Send className="h-7 w-7 text-green-400" />
                </div>
                <p className="mb-2 text-lg font-bold text-text-primary">
                  {lang === 'ar' ? 'شكراً لتواصلك!' : 'Thanks for reaching out!'}
                </p>
                <p className="mb-4 text-sm text-text-secondary">
                  {lang === 'ar' ? 'بنرد عليك بأقرب وقت' : 'We\'ll get back to you soon'}
                </p>
                <button
                  onClick={() => { setSent(false); setName(''); setEmail(''); setMessage('') }}
                  className="text-sm text-status-star hover:underline"
                >
                  {lang === 'ar' ? 'إرسال رسالة أخرى' : 'Send another message'}
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'الاسم' : 'Name'}
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                    placeholder={lang === 'ar' ? 'اسمك الكريم' : 'Your name'}
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'البريد الإلكتروني' : 'Email'}
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                    placeholder={lang === 'ar' ? 'بريدك الإلكتروني' : 'Your email'}
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'الرسالة' : 'Message'}
                  </label>
                  <textarea
                    required
                    rows={5}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                    placeholder={lang === 'ar' ? 'اكتب رسالتك هنا...' : 'Write your message here...'}
                  />
                </div>

                <button
                  type="submit"
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover"
                >
                  <Send className="h-4 w-4" />
                  {lang === 'ar' ? 'إرسال' : 'Send'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
