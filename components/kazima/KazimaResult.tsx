'use client'

import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Copy, Check, Star, Download, RotateCcw } from 'lucide-react'
import type { KazimaMode } from '@/lib/kazima-ai'
import { MODE_LABELS } from '@/lib/kazima-ai'

interface KazimaResultProps {
  mode: KazimaMode
  result: string
  timestamp: string
  onSave?: () => void
  onReset: () => void
  isSaving?: boolean
}

export default function KazimaResult({
  mode,
  result,
  timestamp,
  onSave,
  onReset,
  isSaving,
}: KazimaResultProps) {
  const { lang } = useLanguage()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleDownload() {
    const modeLabel = MODE_LABELS[mode]
    const filename = `kazima-${mode}-${new Date().toISOString().slice(0, 10)}.txt`
    const content = `=== كاظمة AI - ${modeLabel.ar} ===\n${lang === 'ar' ? 'التاريخ' : 'Date'}: ${new Date(timestamp).toLocaleString('ar-EG')}\n\n${result}`
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const modeLabel = MODE_LABELS[mode]

  return (
    <div className="rounded-2xl border border-dark-border bg-dark-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-dark-border px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center rounded-lg bg-status-star/10 border border-status-star/20 px-2.5 py-1 text-xs font-medium text-status-star">
            {lang === 'ar' ? modeLabel.ar : modeLabel.en}
          </span>
          <span className="text-xs text-text-muted" dir="ltr">
            {new Date(timestamp).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
            title={lang === 'ar' ? 'نسخ' : 'Copy'}
          >
            {copied ? <Check className="h-3.5 w-3.5 text-status-success" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? (lang === 'ar' ? 'تم' : 'Copied') : (lang === 'ar' ? 'نسخ' : 'Copy')}
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface hover:text-text-primary"
            title={lang === 'ar' ? 'تحميل' : 'Download'}
          >
            <Download className="h-3.5 w-3.5" />
          </button>
          {onSave && (
            <button
              onClick={onSave}
              disabled={isSaving}
              className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface hover:text-status-star"
              title={lang === 'ar' ? 'حفظ' : 'Save'}
            >
              <Star className="h-3.5 w-3.5" />
              {lang === 'ar' ? 'حفظ' : 'Save'}
            </button>
          )}
        </div>
      </div>

      {/* Result Content */}
      <div
        className="kazima-result px-5 py-4 text-sm leading-[1.9] text-text-primary whitespace-pre-wrap"
        dir="rtl"
      >
        {result}
      </div>

      {/* Footer */}
      <div className="border-t border-dark-border px-5 py-3">
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          {lang === 'ar' ? 'تحليل جديد' : 'New Analysis'}
        </button>
      </div>
    </div>
  )
}
