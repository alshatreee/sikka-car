'use client'

import { useState, useEffect } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import { Plus, Edit, Trash2, Eye, Loader2, BarChart3, CheckCircle, Clock } from 'lucide-react'
import { getArchiveStats } from '@/actions/archiveActions'

interface ArchiveItemRow {
  id: string
  slug: string
  titleAr: string
  itemType: string
  status: string
  creator: string | null
  publicationYear: number | null
  createdAt: string
}

interface Stats {
  totalItems: number
  published: number
  draft: number
  totalFiles: number
  ocrCompleted: number
}

const TYPE_LABELS: Record<string, string> = {
  ARTICLE: 'مقال',
  BOOK: 'كتاب',
  MANUSCRIPT: 'مخطوطة',
  DOCUMENT: 'وثيقة',
  IMAGE: 'صورة',
  AUDIO: 'صوتي',
  VIDEO: 'مرئي',
  PUBLICATION: 'إصدار',
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  DRAFT: { label: 'مسودة', color: 'text-text-muted' },
  REVIEW: { label: 'مراجعة', color: 'text-yellow-400' },
  PUBLISHED: { label: 'منشور', color: 'text-green-400' },
  ARCHIVED: { label: 'مؤرشف', color: 'text-blue-400' },
}

export default function DashboardArchivePage() {
  const { lang } = useLanguage()
  const [items, setItems] = useState<ArchiveItemRow[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    Promise.all([
      fetch(`/api/archive?page=${page}&limit=20`).then((r) => r.json()),
      getArchiveStats(),
    ])
      .then(([itemsData, statsData]) => {
        setItems(itemsData.items || [])
        setTotal(itemsData.total || 0)
        setStats(statsData)
      })
      .finally(() => setLoading(false))
  }, [page])

  async function handleDelete(id: string, title: string) {
    if (!confirm(`حذف "${title}"؟ هذا الإجراء لا يمكن التراجع عنه.`)) return

    const res = await fetch(`/api/archive/item/${id}`, { method: 'DELETE' })
    if (res.ok) {
      setItems((prev) => prev.filter((i) => i.id !== id))
      setTotal((prev) => prev - 1)
    }
  }

  if (loading) {
    return (
      <main className="container py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
        </div>
      </main>
    )
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-lg font-bold text-text-primary">
            {lang === 'ar' ? 'إدارة الأرشيف' : 'Archive Management'}
          </h1>
          <Link
            href="/dashboard/archive/import"
            className="flex items-center gap-1.5 rounded-xl bg-brand-solid px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-brand-solid-hover"
          >
            <Plus className="h-4 w-4" />
            {lang === 'ar' ? 'إضافة عنصر' : 'Add Item'}
          </Link>
        </div>

        {/* Stats */}
        {stats && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {[
              { label: lang === 'ar' ? 'إجمالي العناصر' : 'Total', value: stats.totalItems, icon: BarChart3, color: 'text-status-star' },
              { label: lang === 'ar' ? 'منشور' : 'Published', value: stats.published, icon: CheckCircle, color: 'text-green-400' },
              { label: lang === 'ar' ? 'مسودة' : 'Draft', value: stats.draft, icon: Clock, color: 'text-text-muted' },
              { label: lang === 'ar' ? 'الملفات' : 'Files', value: stats.totalFiles, icon: BarChart3, color: 'text-blue-400' },
              { label: 'OCR', value: stats.ocrCompleted, icon: CheckCircle, color: 'text-purple-400' },
            ].map((stat, i) => (
              <div key={i} className="rounded-xl border border-dark-border bg-dark-card p-3 text-center">
                <stat.icon className={`mx-auto mb-1 h-4 w-4 ${stat.color}`} />
                <p className="text-lg font-bold text-text-primary">{stat.value}</p>
                <p className="text-[10px] text-text-muted">{stat.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Items Table */}
        <div className="rounded-2xl border border-dark-border bg-dark-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dark-border text-text-muted text-xs">
                  <th className="px-4 py-3 text-right">{lang === 'ar' ? 'العنوان' : 'Title'}</th>
                  <th className="px-4 py-3 text-center">{lang === 'ar' ? 'النوع' : 'Type'}</th>
                  <th className="px-4 py-3 text-center">{lang === 'ar' ? 'الحالة' : 'Status'}</th>
                  <th className="px-4 py-3 text-center">{lang === 'ar' ? 'المؤلف' : 'Creator'}</th>
                  <th className="px-4 py-3 text-center">{lang === 'ar' ? 'إجراءات' : 'Actions'}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-dark-border/50 hover:bg-dark-surface/50 transition-colors">
                    <td className="px-4 py-3 text-text-primary font-medium" dir="rtl">
                      {item.titleAr}
                      {item.publicationYear && (
                        <span className="text-text-muted text-[10px] mr-2">({item.publicationYear})</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="rounded-lg bg-dark-surface px-2 py-0.5 text-[10px] text-text-secondary">
                        {TYPE_LABELS[item.itemType] || item.itemType}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs ${STATUS_LABELS[item.status]?.color || 'text-text-muted'}`}>
                        {STATUS_LABELS[item.status]?.label || item.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-xs text-text-secondary" dir="rtl">
                      {item.creator || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <Link
                          href={`/archive/item/${item.slug}`}
                          className="rounded-lg p-1.5 text-text-secondary hover:bg-dark-surface hover:text-text-primary"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Link>
                        <button className="rounded-lg p-1.5 text-text-secondary hover:bg-dark-surface hover:text-text-primary">
                          <Edit className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id, item.titleAr)}
                          className="rounded-lg p-1.5 text-text-secondary hover:bg-red-500/10 hover:text-red-400"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {items.length === 0 && (
            <div className="p-12 text-center">
              <p className="text-sm text-text-muted">
                {lang === 'ar' ? 'لا توجد عناصر. أضف أول عنصر.' : 'No items yet. Add the first one.'}
              </p>
            </div>
          )}
        </div>

        {/* Pagination */}
        {total > 20 && (
          <div className="mt-4 flex items-center justify-center gap-4 text-xs text-text-secondary">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-lg border border-dark-border px-3 py-1 disabled:opacity-30 hover:bg-dark-surface"
            >
              {lang === 'ar' ? 'السابق' : 'Previous'}
            </button>
            <span>{page} / {Math.ceil(total / 20)}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(total / 20)}
              className="rounded-lg border border-dark-border px-3 py-1 disabled:opacity-30 hover:bg-dark-surface"
            >
              {lang === 'ar' ? 'التالي' : 'Next'}
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
