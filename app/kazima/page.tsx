'use client'

import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import {
  BookOpen,
  History,
  Sparkles,
  MessageCircle,
  GitBranch,
  Search,
} from 'lucide-react'
import KazimaInput from '@/components/kazima/KazimaInput'
import KazimaResult from '@/components/kazima/KazimaResult'
import KazimaHistory from '@/components/kazima/KazimaHistory'
import { saveKazimaAnalysis } from '@/actions/kazimaActions'
import type { KazimaMode, KazimaResponse } from '@/lib/kazima-ai'

type Tab = 'analyze' | 'history'

export default function KazimaPage() {
  const { lang } = useLanguage()
  const [tab, setTab] = useState<Tab>('analyze')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [response, setResponse] = useState<KazimaResponse | null>(null)
  const [lastInput, setLastInput] = useState<{ mode: KazimaMode; text: string; context?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(mode: KazimaMode, text: string, additionalContext?: string) {
    setIsLoading(true)
    setError(null)
    setLastInput({ mode, text, context: additionalContext })

    try {
      const res = await fetch('/api/kazima-ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, text, additionalContext }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'حدث خطأ غير متوقع')
        return
      }

      setResponse(data)
    } catch {
      setError(lang === 'ar' ? 'فشل الاتصال بالخادم' : 'Failed to connect to server')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleSave() {
    if (!response || !lastInput) return
    setIsSaving(true)
    try {
      const result = await saveKazimaAnalysis({
        mode: lastInput.mode,
        inputText: lastInput.text,
        result: response.result,
        additionalContext: lastInput.context,
      })
      if (!result.success) {
        setError(result.error || (lang === 'ar' ? 'فشل الحفظ. سجّل دخولك أولاً.' : 'Save failed. Please sign in.'))
      }
    } catch {
      setError(lang === 'ar' ? 'فشل حفظ التحليل' : 'Failed to save analysis')
    }
    setIsSaving(false)
  }

  function handleReset() {
    setResponse(null)
    setLastInput(null)
    setError(null)
  }

  const tools = [
    {
      href: '/kazima/analyze',
      icon: GitBranch,
      title: lang === 'ar' ? 'التحليل الشامل' : 'Full Analysis',
      desc: lang === 'ar' ? 'كيانات + علاقات + زمن + تصنيف + شبكة معرفية' : 'Entities + Relations + Timeline + Classification + Graph',
      color: 'text-purple-400',
      bg: 'bg-purple-500/10 border-purple-500/20',
    },
    {
      href: '/kazima/chat',
      icon: MessageCircle,
      title: lang === 'ar' ? 'محادثة كاظمة' : 'Kazima Chat',
      desc: lang === 'ar' ? 'اسأل عن المخطوطات والتاريخ الخليجي' : 'Ask about manuscripts & Gulf history',
      color: 'text-green-400',
      bg: 'bg-green-500/10 border-green-500/20',
    },
  ]

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-status-star/10 border border-status-star/20">
            <BookOpen className="h-8 w-8 text-status-star" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'كاظمة' : 'Kazima'}
            <span className="text-status-star"> AI</span>
          </h1>
          <p className="text-sm text-text-secondary">
            {lang === 'ar'
              ? 'مساعد بحثي متخصص في التاريخ الديني الخليجي وتحقيق المخطوطات'
              : 'Scholarly research assistant for Gulf religious history & manuscript studies'}
          </p>
        </div>

        {/* Quick Tools */}
        <div className="mb-6 grid gap-3 sm:grid-cols-2">
          {tools.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="group flex items-start gap-3 rounded-2xl border border-dark-border bg-dark-card p-4 transition-all hover:border-dark-border-light"
            >
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${tool.bg}`}>
                <tool.icon className={`h-5 w-5 ${tool.color}`} />
              </div>
              <div>
                <h3 className="text-sm font-medium text-text-primary group-hover:text-status-star transition-colors">
                  {tool.title}
                </h3>
                <p className="text-xs text-text-muted mt-0.5">{tool.desc}</p>
              </div>
            </Link>
          ))}
        </div>

        {/* Tabs */}
        <div className="mb-6 flex items-center gap-2 rounded-xl border border-dark-border bg-dark-card p-1">
          <button
            onClick={() => setTab('analyze')}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
              tab === 'analyze'
                ? 'bg-dark-surface text-text-primary shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <Sparkles className="h-4 w-4" />
            {lang === 'ar' ? 'تحليل بسيط' : 'Quick Analysis'}
          </button>
          <button
            onClick={() => setTab('history')}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
              tab === 'history'
                ? 'bg-dark-surface text-text-primary shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <History className="h-4 w-4" />
            {lang === 'ar' ? 'السجل' : 'History'}
          </button>
        </div>

        {/* Content */}
        {tab === 'analyze' ? (
          <div className="space-y-6">
            {/* Input Form */}
            {!response && (
              <div className="rounded-2xl border border-dark-border bg-dark-card p-5">
                <KazimaInput onSubmit={handleSubmit} isLoading={isLoading} />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
                {error}
              </div>
            )}

            {/* Loading */}
            {isLoading && (
              <div className="rounded-2xl border border-dark-border bg-dark-card p-8">
                <div className="flex flex-col items-center justify-center gap-4">
                  <div className="relative">
                    <div className="h-12 w-12 animate-spin rounded-full border-2 border-dark-border border-t-status-star" />
                    <BookOpen className="absolute inset-0 m-auto h-5 w-5 text-status-star" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-text-primary">
                      {lang === 'ar' ? 'جارٍ التحليل...' : 'Analyzing...'}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {lang === 'ar'
                        ? 'كاظمة AI يعمل على تحليل النص'
                        : 'Kazima AI is processing your text'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Result */}
            {response && !isLoading && (
              <KazimaResult
                mode={response.mode}
                result={response.result}
                timestamp={response.timestamp}
                onSave={handleSave}
                onReset={handleReset}
                isSaving={isSaving}
              />
            )}

            {/* Features Overview (when no result shown) */}
            {!response && !isLoading && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  {
                    title: lang === 'ar' ? 'تحليل نصي نقدي' : 'Critical Text Analysis',
                    desc: lang === 'ar' ? 'كشف التصحيف والسقط والتحريف' : 'Detect scribal errors & corruption',
                  },
                  {
                    title: lang === 'ar' ? 'استخراج بيانات' : 'Data Extraction',
                    desc: lang === 'ar' ? 'أعلام، أماكن، تواريخ، كتب' : 'Names, places, dates, books',
                  },
                  {
                    title: lang === 'ar' ? 'حواشٍ علمية' : 'Scholarly Annotations',
                    desc: lang === 'ar' ? 'حواشٍ توضيحية مختصرة ودقيقة' : 'Concise scholarly footnotes',
                  },
                  {
                    title: lang === 'ar' ? 'صياغة للنشر' : 'Publication Ready',
                    desc: lang === 'ar' ? 'صياغة أكاديمية للمجلات المحكّمة' : 'Academic writing for journals',
                  },
                  {
                    title: lang === 'ar' ? 'خبير مخطوطات' : 'Manuscript Expert',
                    desc: lang === 'ar' ? 'تحليل الفترة والمدرسة والتقليد' : 'Period, school & tradition analysis',
                  },
                  {
                    title: lang === 'ar' ? 'محتوى رقمي' : 'Digital Content',
                    desc: lang === 'ar' ? 'تحويل المحتوى لسلايدات سوشيال' : 'Convert to social media slides',
                  },
                ].map((feature, i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-dark-border bg-dark-card p-4 transition-colors hover:border-dark-border-light"
                  >
                    <h3 className="mb-1 text-sm font-medium text-text-primary">{feature.title}</h3>
                    <p className="text-xs text-text-muted">{feature.desc}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <KazimaHistory />
        )}
      </div>
    </main>
  )
}
