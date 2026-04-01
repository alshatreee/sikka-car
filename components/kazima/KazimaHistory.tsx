'use client'

import { useState, useEffect } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Clock, Star, Trash2, Eye, ChevronLeft, ChevronRight } from 'lucide-react'
import { getKazimaAnalyses, toggleKazimaFavorite, deleteKazimaAnalysis } from '@/actions/kazimaActions'
import { MODE_LABELS } from '@/lib/kazima-ai'
import type { KazimaMode } from '@/lib/kazima-ai'

interface Analysis {
  id: string
  mode: string
  inputText: string
  result: string
  title: string | null
  isFavorite: boolean
  createdAt: Date
}

export default function KazimaHistory() {
  const { lang } = useLanguage()
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const limit = 10

  useEffect(() => {
    loadAnalyses()
  }, [page])

  async function loadAnalyses() {
    setLoading(true)
    try {
      const data = await getKazimaAnalyses(page, limit)
      setAnalyses(data.analyses as Analysis[])
      setTotal(data.total)
    } catch {
      // User not signed in or error
    }
    setLoading(false)
  }

  async function handleToggleFavorite(id: string) {
    await toggleKazimaFavorite(id)
    setAnalyses((prev) =>
      prev.map((a) => (a.id === id ? { ...a, isFavorite: !a.isFavorite } : a))
    )
  }

  async function handleDelete(id: string) {
    await deleteKazimaAnalysis(id)
    setAnalyses((prev) => prev.filter((a) => a.id !== id))
    setTotal((prev) => prev - 1)
    if (selectedId === id) setSelectedId(null)
  }

  const totalPages = Math.ceil(total / limit)
  const selected = analyses.find((a) => a.id === selectedId)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-dark-border border-t-status-star" />
      </div>
    )
  }

  if (analyses.length === 0) {
    return (
      <div className="rounded-2xl border border-dark-border bg-dark-card p-8 text-center">
        <Clock className="mx-auto mb-3 h-10 w-10 text-text-muted" />
        <p className="text-sm text-text-secondary">
          {lang === 'ar' ? 'لا توجد تحليلات محفوظة بعد' : 'No saved analyses yet'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Selected Analysis Detail */}
      {selected && (
        <div className="rounded-2xl border border-status-star/30 bg-dark-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-dark-border px-5 py-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-status-star">
                {MODE_LABELS[selected.mode as KazimaMode]?.ar || selected.mode}
              </span>
              <span className="text-xs text-text-muted">
                {new Date(selected.createdAt).toLocaleDateString('ar-EG')}
              </span>
            </div>
            <button
              onClick={() => setSelectedId(null)}
              className="text-xs text-text-secondary hover:text-text-primary"
            >
              {lang === 'ar' ? 'إغلاق' : 'Close'}
            </button>
          </div>
          <div className="p-5">
            <div className="mb-3 rounded-xl bg-dark-surface p-3 text-xs text-text-secondary" dir="rtl">
              <span className="font-medium text-text-muted">
                {lang === 'ar' ? 'النص الأصلي: ' : 'Original: '}
              </span>
              {selected.inputText.slice(0, 200)}
              {selected.inputText.length > 200 ? '...' : ''}
            </div>
            <div className="text-sm leading-[1.9] text-text-primary whitespace-pre-wrap" dir="rtl">
              {selected.result}
            </div>
          </div>
        </div>
      )}

      {/* Analysis List */}
      <div className="space-y-2">
        {analyses.map((analysis) => (
          <div
            key={analysis.id}
            className={`group flex items-center justify-between rounded-xl border px-4 py-3 transition-all ${
              selectedId === analysis.id
                ? 'border-status-star/30 bg-status-star/5'
                : 'border-dark-border bg-dark-card hover:border-dark-border-light'
            }`}
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <span className="shrink-0 rounded-lg bg-dark-surface px-2 py-1 text-[10px] font-medium text-text-secondary">
                {MODE_LABELS[analysis.mode as KazimaMode]?.ar || analysis.mode}
              </span>
              <span className="truncate text-xs text-text-secondary" dir="rtl">
                {analysis.title || analysis.inputText.slice(0, 60)}
              </span>
              <span className="shrink-0 text-[10px] text-text-muted">
                {new Date(analysis.createdAt).toLocaleDateString('ar-EG')}
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={() => setSelectedId(selectedId === analysis.id ? null : analysis.id)}
                className="rounded-lg p-1.5 text-text-secondary hover:bg-dark-surface hover:text-text-primary"
              >
                <Eye className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => handleToggleFavorite(analysis.id)}
                className={`rounded-lg p-1.5 transition-colors ${
                  analysis.isFavorite
                    ? 'text-status-star hover:bg-dark-surface'
                    : 'text-text-secondary hover:bg-dark-surface hover:text-status-star'
                }`}
              >
                <Star className={`h-3.5 w-3.5 ${analysis.isFavorite ? 'fill-current' : ''}`} />
              </button>
              <button
                onClick={() => handleDelete(analysis.id)}
                className="rounded-lg p-1.5 text-text-secondary hover:bg-red-500/10 hover:text-red-400"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-dark-border p-1.5 text-text-secondary disabled:opacity-30 hover:bg-dark-surface"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <span className="text-xs text-text-secondary">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-dark-border p-1.5 text-text-secondary disabled:opacity-30 hover:bg-dark-surface"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
