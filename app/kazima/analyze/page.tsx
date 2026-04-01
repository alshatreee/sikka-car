'use client'

import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import {
  Send,
  Loader2,
  BookOpen,
  ArrowRight,
  Users,
  MapPin,
  BookMarked,
  Calendar,
  Tag,
  GitBranch,
  AlertTriangle,
} from 'lucide-react'

interface FullAnalysisResult {
  entities: {
    persons: string[]
    locations: string[]
    books: string[]
    tribes: string[]
    dates: string[]
    keywords: string[]
    text_type: string
    confidence_level: string
  }
  relations: {
    relations: {
      from: string
      to: string
      type: string
      uncertain?: boolean
    }[]
  }
  timeline: {
    timeline: {
      event: string
      year: string
      calendar: string
      approximate?: boolean
    }[]
  }
  classification: {
    classification: {
      primary: string
      secondary: string[]
      region: string
      period: string
      importance: string
    }
  }
  graph: {
    nodes: { id: string; type: string; label: string }[]
    edges: { source: string; target: string; type: string; uncertain?: boolean }[]
  }
}

export default function FullAnalysisPage() {
  const { lang } = useLanguage()
  const [text, setText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<FullAnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'entities' | 'relations' | 'timeline' | 'classification' | 'graph'>('entities')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim() || isLoading) return

    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch('/api/kazima-ai/analyze-full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'حدث خطأ')
        return
      }

      setResult(data)
    } catch {
      setError(lang === 'ar' ? 'فشل الاتصال بالخادم' : 'Connection failed')
    } finally {
      setIsLoading(false)
    }
  }

  const tabs = [
    { key: 'entities' as const, label: lang === 'ar' ? 'الكيانات' : 'Entities', icon: Users },
    { key: 'relations' as const, label: lang === 'ar' ? 'العلاقات' : 'Relations', icon: GitBranch },
    { key: 'timeline' as const, label: lang === 'ar' ? 'الزمن' : 'Timeline', icon: Calendar },
    { key: 'classification' as const, label: lang === 'ar' ? 'التصنيف' : 'Classification', icon: Tag },
    { key: 'graph' as const, label: lang === 'ar' ? 'الشبكة' : 'Graph', icon: GitBranch },
  ]

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-status-star/10 border border-status-star/20">
              <BookOpen className="h-5 w-5 text-status-star" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'التحليل الشامل' : 'Full Analysis'}
              </h1>
              <p className="text-xs text-text-muted">
                {lang === 'ar'
                  ? 'استخراج الكيانات + العلاقات + الزمن + التصنيف'
                  : 'Entities + Relations + Timeline + Classification'}
              </p>
            </div>
          </div>
          <Link
            href="/kazima"
            className="flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'الرئيسية' : 'Main'}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {/* Input Form */}
        {!result && (
          <form onSubmit={handleSubmit} className="mb-6 rounded-2xl border border-dark-border bg-dark-card p-5">
            <label className="mb-2 block text-sm font-medium text-text-primary">
              {lang === 'ar' ? 'أدخل النص للتحليل الشامل' : 'Enter text for full analysis'}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              className="mb-4 w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm leading-relaxed text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
              placeholder={lang === 'ar' ? 'الصق النص هنا...' : 'Paste your text here...'}
              dir="rtl"
            />
            <button
              type="submit"
              disabled={!text.trim() || isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {lang === 'ar' ? 'جارٍ التحليل الشامل (4 عمليات متوازية)...' : 'Running full analysis (4 parallel operations)...'}
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  {lang === 'ar' ? 'تحليل شامل' : 'Full Analysis'}
                </>
              )}
            </button>
          </form>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">{error}</div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="rounded-2xl border border-dark-border bg-dark-card p-8">
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                <div className="h-14 w-14 animate-spin rounded-full border-2 border-dark-border border-t-status-star" />
                <BookOpen className="absolute inset-0 m-auto h-6 w-6 text-status-star" />
              </div>
              <p className="text-sm text-text-secondary">
                {lang === 'ar' ? 'كاظمة AI يحلل النص بالكامل...' : 'Kazima AI is analyzing the full text...'}
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {['الكيانات', 'العلاقات', 'الزمن', 'التصنيف'].map((step, i) => (
                  <span key={i} className="rounded-lg bg-dark-surface px-2.5 py-1 text-[10px] text-text-muted animate-pulse">
                    {step}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {result && !isLoading && (
          <div className="space-y-4">
            {/* Reset button */}
            <button
              onClick={() => { setResult(null); setText('') }}
              className="text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              {lang === 'ar' ? '← تحليل جديد' : '← New Analysis'}
            </button>

            {/* Tabs */}
            <div className="flex gap-1 overflow-x-auto rounded-xl border border-dark-border bg-dark-card p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-xs font-medium transition-all ${
                    activeTab === tab.key
                      ? 'bg-dark-surface text-text-primary shadow-sm'
                      : 'text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="rounded-2xl border border-dark-border bg-dark-card p-5">
              {/* Entities Tab */}
              {activeTab === 'entities' && result.entities && (
                <div className="space-y-4">
                  <EntitySection icon={Users} label={lang === 'ar' ? 'الأشخاص' : 'Persons'} items={result.entities.persons} color="text-blue-400" />
                  <EntitySection icon={MapPin} label={lang === 'ar' ? 'الأماكن' : 'Locations'} items={result.entities.locations} color="text-green-400" />
                  <EntitySection icon={BookMarked} label={lang === 'ar' ? 'الكتب' : 'Books'} items={result.entities.books} color="text-purple-400" />
                  <EntitySection icon={Users} label={lang === 'ar' ? 'القبائل' : 'Tribes'} items={result.entities.tribes} color="text-orange-400" />
                  <EntitySection icon={Calendar} label={lang === 'ar' ? 'التواريخ' : 'Dates'} items={result.entities.dates} color="text-red-400" />
                  <EntitySection icon={Tag} label={lang === 'ar' ? 'الكلمات المفتاحية' : 'Keywords'} items={result.entities.keywords} color="text-status-star" />

                  <div className="flex gap-4 border-t border-dark-border pt-3 text-xs text-text-muted">
                    <span>{lang === 'ar' ? 'نوع النص:' : 'Text type:'} <strong className="text-text-secondary">{result.entities.text_type}</strong></span>
                    <span>{lang === 'ar' ? 'الثقة:' : 'Confidence:'} <strong className="text-text-secondary">{result.entities.confidence_level}</strong></span>
                  </div>
                </div>
              )}

              {/* Relations Tab */}
              {activeTab === 'relations' && result.relations && (
                <div className="space-y-2">
                  {result.relations.relations?.length > 0 ? (
                    result.relations.relations.map((rel, i) => (
                      <div key={i} className="flex items-center gap-2 rounded-xl bg-dark-surface p-3 text-sm" dir="rtl">
                        <span className="font-medium text-text-primary">{rel.from}</span>
                        <span className="rounded bg-status-star/10 px-2 py-0.5 text-[10px] text-status-star">{rel.type}</span>
                        <span className="text-text-muted">→</span>
                        <span className="font-medium text-text-primary">{rel.to}</span>
                        {rel.uncertain && (
                          <AlertTriangle className="h-3 w-3 text-status-warning" title="غير مؤكد" />
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted text-center py-4">
                      {lang === 'ar' ? 'لم يتم العثور على علاقات' : 'No relations found'}
                    </p>
                  )}
                </div>
              )}

              {/* Timeline Tab */}
              {activeTab === 'timeline' && result.timeline && (
                <div className="space-y-3">
                  {result.timeline.timeline?.length > 0 ? (
                    result.timeline.timeline.map((event, i) => (
                      <div key={i} className="flex items-start gap-3 rounded-xl bg-dark-surface p-3" dir="rtl">
                        <div className="flex h-8 min-w-[60px] items-center justify-center rounded-lg bg-status-star/10 border border-status-star/20 text-xs font-bold text-status-star">
                          {event.year}
                        </div>
                        <div>
                          <p className="text-sm text-text-primary">{event.event}</p>
                          <div className="mt-1 flex gap-2">
                            <span className="text-[10px] text-text-muted">{event.calendar}</span>
                            {event.approximate && (
                              <span className="text-[10px] text-status-warning">≈ {lang === 'ar' ? 'تقريبي' : 'approximate'}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-text-muted text-center py-4">
                      {lang === 'ar' ? 'لم يتم العثور على أحداث زمنية' : 'No timeline events found'}
                    </p>
                  )}
                </div>
              )}

              {/* Classification Tab */}
              {activeTab === 'classification' && result.classification?.classification && (
                <div className="space-y-4" dir="rtl">
                  <div className="rounded-xl bg-dark-surface p-4">
                    <p className="text-xs text-text-muted mb-1">{lang === 'ar' ? 'التصنيف الأساسي' : 'Primary'}</p>
                    <p className="text-lg font-bold text-status-star">{result.classification.classification.primary}</p>
                  </div>
                  {result.classification.classification.secondary?.length > 0 && (
                    <div>
                      <p className="text-xs text-text-muted mb-2">{lang === 'ar' ? 'تصنيفات ثانوية' : 'Secondary'}</p>
                      <div className="flex flex-wrap gap-2">
                        {result.classification.classification.secondary.map((s, i) => (
                          <span key={i} className="rounded-lg bg-dark-surface border border-dark-border px-2.5 py-1 text-xs text-text-secondary">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-3">
                    <InfoBox label={lang === 'ar' ? 'المنطقة' : 'Region'} value={result.classification.classification.region} />
                    <InfoBox label={lang === 'ar' ? 'الفترة' : 'Period'} value={result.classification.classification.period} />
                    <InfoBox label={lang === 'ar' ? 'الأهمية' : 'Importance'} value={result.classification.classification.importance} />
                  </div>
                </div>
              )}

              {/* Graph Tab */}
              {activeTab === 'graph' && result.graph && (
                <div className="space-y-4" dir="rtl">
                  <p className="text-xs text-text-muted">
                    {lang === 'ar'
                      ? `${result.graph.nodes.length} عقدة، ${result.graph.edges.length} علاقة`
                      : `${result.graph.nodes.length} nodes, ${result.graph.edges.length} edges`}
                  </p>

                  {/* Nodes */}
                  <div>
                    <p className="text-xs font-medium text-text-secondary mb-2">{lang === 'ar' ? 'العقد' : 'Nodes'}</p>
                    <div className="flex flex-wrap gap-2">
                      {result.graph.nodes.map((node, i) => (
                        <span
                          key={i}
                          className={`rounded-lg px-2.5 py-1 text-xs border ${
                            node.type === 'person'
                              ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                              : node.type === 'location'
                              ? 'bg-green-500/10 border-green-500/20 text-green-400'
                              : node.type === 'book'
                              ? 'bg-purple-500/10 border-purple-500/20 text-purple-400'
                              : 'bg-orange-500/10 border-orange-500/20 text-orange-400'
                          }`}
                        >
                          {node.label}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Edges */}
                  {result.graph.edges.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-text-secondary mb-2">{lang === 'ar' ? 'الروابط' : 'Edges'}</p>
                      <div className="space-y-1.5">
                        {result.graph.edges.map((edge, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs text-text-secondary">
                            <span className="font-medium text-text-primary">{edge.source}</span>
                            <span className="rounded bg-dark-surface px-1.5 py-0.5 text-[10px]">{edge.type}</span>
                            <span>→</span>
                            <span className="font-medium text-text-primary">{edge.target}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  )
}

function EntitySection({ icon: Icon, label, items, color }: {
  icon: typeof Users
  label: string
  items: string[]
  color: string
}) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className="text-xs font-medium text-text-secondary">{label}</span>
        <span className="rounded-full bg-dark-surface px-1.5 py-0.5 text-[10px] text-text-muted">{items.length}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span key={i} className="rounded-lg bg-dark-surface border border-dark-border px-2.5 py-1 text-xs text-text-primary">
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-dark-surface p-3 text-center">
      <p className="text-[10px] text-text-muted mb-0.5">{label}</p>
      <p className="text-xs font-medium text-text-primary">{value || '—'}</p>
    </div>
  )
}
