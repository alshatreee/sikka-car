'use client'

import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Send, Loader2, ChevronDown } from 'lucide-react'
import type { KazimaMode } from '@/lib/kazima-ai'
import { MODE_LABELS } from '@/lib/kazima-ai'

interface KazimaInputProps {
  onSubmit: (mode: KazimaMode, text: string, additionalContext?: string) => void
  isLoading: boolean
}

export default function KazimaInput({ onSubmit, isLoading }: KazimaInputProps) {
  const { lang } = useLanguage()
  const [mode, setMode] = useState<KazimaMode>('analysis')
  const [text, setText] = useState('')
  const [additionalContext, setAdditionalContext] = useState('')
  const [showContext, setShowContext] = useState(false)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim() || isLoading) return
    onSubmit(mode, text.trim(), additionalContext.trim() || undefined)
  }

  const modes = Object.entries(MODE_LABELS) as [KazimaMode, typeof MODE_LABELS[KazimaMode]][]

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Mode Selection */}
      <div>
        <label className="mb-2 block text-sm font-medium text-text-primary">
          {lang === 'ar' ? 'وضع التحليل' : 'Analysis Mode'}
        </label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {modes.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setMode(key)}
              className={`rounded-xl border px-3 py-2.5 text-xs font-medium transition-all ${
                mode === key
                  ? 'border-status-star bg-status-star/10 text-status-star'
                  : 'border-dark-border bg-dark-surface text-text-secondary hover:border-dark-border-light hover:text-text-primary'
              }`}
            >
              <span className="block">{lang === 'ar' ? label.ar : label.en}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-text-muted">
          {MODE_LABELS[mode].description}
        </p>
      </div>

      {/* Text Input */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-primary">
          {lang === 'ar' ? 'النص' : 'Text'}
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm leading-relaxed text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
          placeholder={
            lang === 'ar'
              ? 'أدخل النص المراد تحليله هنا...'
              : 'Enter the text to analyze...'
          }
          dir="rtl"
        />
        <div className="mt-1 flex justify-between text-xs text-text-muted">
          <span>
            {text.length > 0
              ? lang === 'ar'
                ? `${text.length.toLocaleString('ar-EG')} حرف`
                : `${text.length.toLocaleString()} characters`
              : ''}
          </span>
          <span>{lang === 'ar' ? 'الحد الأقصى: 50,000 حرف' : 'Max: 50,000 characters'}</span>
        </div>
      </div>

      {/* Additional Context Toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowContext(!showContext)}
          className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
        >
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showContext ? 'rotate-180' : ''}`} />
          {lang === 'ar' ? 'إضافة سياق إضافي (اختياري)' : 'Add additional context (optional)'}
        </button>
        {showContext && (
          <textarea
            value={additionalContext}
            onChange={(e) => setAdditionalContext(e.target.value)}
            rows={3}
            className="mt-2 w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
            placeholder={
              lang === 'ar'
                ? 'معلومات إضافية عن النص أو المخطوطة...'
                : 'Additional information about the text or manuscript...'
            }
            dir="rtl"
          />
        )}
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!text.trim() || isLoading}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {lang === 'ar' ? 'جارٍ التحليل...' : 'Analyzing...'}
          </>
        ) : (
          <>
            <Send className="h-4 w-4" />
            {lang === 'ar' ? 'تحليل' : 'Analyze'}
          </>
        )}
      </button>
    </form>
  )
}
