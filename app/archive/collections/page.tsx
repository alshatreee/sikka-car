'use client'

import { useState, useEffect } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import { Library, ArrowRight, Loader2 } from 'lucide-react'
import { getArchiveCollections } from '@/actions/archiveActions'

interface Collection {
  id: string
  nameAr: string
  nameEn: string | null
  descriptionAr: string | null
  slug: string
  coverImage: string | null
  itemCount: number
}

export default function CollectionsPage() {
  const { lang } = useLanguage()
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getArchiveCollections()
      .then((data) => setCollections(data as Collection[]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 border border-purple-500/20">
              <Library className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'المجموعات' : 'Collections'}
              </h1>
              <p className="text-xs text-text-muted">
                {lang === 'ar' ? 'تصفح المجموعات الأرشيفية' : 'Browse archive collections'}
              </p>
            </div>
          </div>
          <Link
            href="/archive"
            className="flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'الأرشيف' : 'Archive'}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
          </div>
        ) : collections.length === 0 ? (
          <div className="rounded-2xl border border-dark-border bg-dark-card p-12 text-center">
            <Library className="mx-auto mb-3 h-10 w-10 text-text-muted" />
            <p className="text-sm text-text-secondary">
              {lang === 'ar' ? 'لا توجد مجموعات بعد' : 'No collections yet'}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {collections.map((col) => (
              <div
                key={col.id}
                className="group rounded-2xl border border-dark-border bg-dark-card p-5 transition-all hover:border-dark-border-light"
              >
                {col.coverImage && (
                  <div className="mb-3 h-32 rounded-xl bg-dark-surface overflow-hidden">
                    <img src={col.coverImage} alt={col.nameAr} className="h-full w-full object-cover" />
                  </div>
                )}
                <h3 className="text-sm font-bold text-text-primary group-hover:text-status-star transition-colors" dir="rtl">
                  {lang === 'ar' ? col.nameAr : col.nameEn || col.nameAr}
                </h3>
                {col.descriptionAr && (
                  <p className="mt-1 text-xs text-text-muted line-clamp-2" dir="rtl">{col.descriptionAr}</p>
                )}
                <p className="mt-2 text-[10px] text-text-muted">
                  {col.itemCount} {lang === 'ar' ? 'عنصر' : 'items'}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
