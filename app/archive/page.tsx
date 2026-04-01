'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Library, Search, Users, BookOpen, Filter, Loader2 } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ArchiveItemType =
  | 'ARTICLE'
  | 'BOOK'
  | 'MANUSCRIPT'
  | 'DOCUMENT'
  | 'IMAGE'
  | 'AUDIO'
  | 'VIDEO'
  | 'PUBLICATION'

interface ArchiveItemCard {
  id: string
  slug: string
  titleAr: string
  titleEn: string | null
  itemType: string
  creator: string | null
  publicationYear: number | null
  coverImageUrl: string | null
  thumbnailUrl: string | null
  status: string
}

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------

const TYPE_LABELS: Record<ArchiveItemType, { ar: string; en: string }> = {
  ARTICLE: { ar: 'مقال', en: 'Article' },
  BOOK: { ar: 'كتاب', en: 'Book' },
  MANUSCRIPT: { ar: 'مخطوطة', en: 'Manuscript' },
  DOCUMENT: { ar: 'وثيقة', en: 'Document' },
  IMAGE: { ar: 'صورة', en: 'Image' },
  AUDIO: { ar: 'صوت', en: 'Audio' },
  VIDEO: { ar: 'فيديو', en: 'Video' },
  PUBLICATION: { ar: 'منشور', en: 'Publication' },
}

const ALL_TYPES: ArchiveItemType[] = [
  'ARTICLE',
  'BOOK',
  'MANUSCRIPT',
  'DOCUMENT',
  'IMAGE',
  'AUDIO',
  'VIDEO',
  'PUBLICATION',
]

// ---------------------------------------------------------------------------
// ArchiveCard
// ---------------------------------------------------------------------------

function ArchiveCard({
  item,
  lang,
}: {
  item: ArchiveItemCard
  lang: 'ar' | 'en'
}) {
  const title = lang === 'ar' ? item.titleAr : (item.titleEn ?? item.titleAr)
  const imageUrl = item.thumbnailUrl ?? item.coverImageUrl
  const typeLabel =
    TYPE_LABELS[item.itemType as ArchiveItemType]?.[lang] ?? item.itemType

  return (
    <Link
      href={`/archive/item/${item.slug}`}
      className="group rounded-2xl border border-dark-border bg-dark-card transition-all hover:border-status-star/40 hover:shadow-lg"
    >
      {/* Thumbnail */}
      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-t-2xl bg-dark-surface">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={title}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <BookOpen className="h-12 w-12 text-text-muted" />
          </div>
        )}
        {/* Type badge */}
        <span className="absolute start-3 top-3 rounded-lg bg-dark-card/80 px-2.5 py-1 text-xs font-medium text-text-secondary backdrop-blur-sm">
          {typeLabel}
        </span>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="mb-1 line-clamp-2 text-base font-semibold text-text-primary transition-colors group-hover:text-status-star">
          {title}
        </h3>
        {item.creator && (
          <p className="mb-1 text-sm text-text-secondary line-clamp-1">
            {item.creator}
          </p>
        )}
        {item.publicationYear && (
          <p className="text-xs text-text-muted">{item.publicationYear}</p>
        )}
      </div>
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ArchiveBrowsePage() {
  const { lang } = useLanguage()

  const [items, setItems] = useState<ArchiveItemCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [activeType, setActiveType] = useState<ArchiveItemType | 'ALL'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  // Fetch items ---------------------------------------------------------------

  const fetchItems = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      const res = await fetch('/api/archive')
      if (!res.ok) throw new Error('Failed to fetch')
      const data: ArchiveItemCard[] = await res.json()
      setItems(data)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  // Derived data --------------------------------------------------------------

  const filteredItems =
    activeType === 'ALL'
      ? items
      : items.filter((item) => item.itemType === activeType)

  const typeCounts = items.reduce<Record<string, number>>((acc, item) => {
    acc[item.itemType] = (acc[item.itemType] || 0) + 1
    return acc
  }, {})

  // Render --------------------------------------------------------------------

  return (
    <main
      className="container py-8 pb-24 md:pb-8"
      dir={lang === 'ar' ? 'rtl' : 'ltr'}
    >
      {/* ---- Header ---- */}
      <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-status-star/10">
              <Library className="h-6 w-6 text-status-star" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-text-primary">
                {lang === 'ar' ? 'الأرشيف' : 'Archive'}
              </h1>
              <p className="text-text-secondary">
                {lang === 'ar'
                  ? 'تصفح المجموعة الرقمية'
                  : 'Browse the digital collection'}
              </p>
            </div>
          </div>

          {/* Quick links */}
          <div className="flex items-center gap-2">
            <Link
              href="/archive/collections"
              className="inline-flex items-center gap-1.5 rounded-xl border border-dark-border bg-dark-surface px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:border-status-star/40 hover:text-status-star"
            >
              <BookOpen className="h-4 w-4" />
              {lang === 'ar' ? 'المجموعات' : 'Collections'}
            </Link>
            <Link
              href="/archive/people"
              className="inline-flex items-center gap-1.5 rounded-xl border border-dark-border bg-dark-surface px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:border-status-star/40 hover:text-status-star"
            >
              <Users className="h-4 w-4" />
              {lang === 'ar' ? 'الأشخاص' : 'People'}
            </Link>
          </div>
        </div>
      </div>

      {/* ---- Search bar ---- */}
      <div className="mb-6">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (searchQuery.trim()) {
              window.location.href = `/archive/search?q=${encodeURIComponent(searchQuery.trim())}`
            }
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute start-3 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                lang === 'ar'
                  ? 'ابحث في الأرشيف...'
                  : 'Search the archive...'
              }
              className="w-full rounded-xl border border-dark-border bg-dark-surface py-3 pe-4 ps-10 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-status-star/50"
            />
          </div>
          <button
            type="submit"
            className="inline-flex items-center gap-2 rounded-xl bg-brand-solid px-5 py-3 font-medium text-white transition-opacity hover:opacity-90"
          >
            <Search className="h-4 w-4" />
            {lang === 'ar' ? 'بحث' : 'Search'}
          </button>
        </form>
      </div>

      {/* ---- Type filters ---- */}
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Filter className="h-4 w-4 text-text-muted" />
        <button
          onClick={() => setActiveType('ALL')}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
            activeType === 'ALL'
              ? 'bg-status-star text-dark-bg'
              : 'border border-dark-border bg-dark-surface text-text-secondary hover:border-status-star/40'
          }`}
        >
          {lang === 'ar' ? 'الكل' : 'All'}
          <span className="ms-1 opacity-70">({items.length})</span>
        </button>
        {ALL_TYPES.map((type) => {
          const count = typeCounts[type] || 0
          if (count === 0) return null
          return (
            <button
              key={type}
              onClick={() => setActiveType(type)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                activeType === type
                  ? 'bg-status-star text-dark-bg'
                  : 'border border-dark-border bg-dark-surface text-text-secondary hover:border-status-star/40'
              }`}
            >
              {TYPE_LABELS[type][lang]}
              <span className="ms-1 opacity-70">({count})</span>
            </button>
          )
        })}
      </div>

      {/* ---- Loading state ---- */}
      {loading && (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-status-star" />
        </div>
      )}

      {/* ---- Error state ---- */}
      {!loading && error && (
        <div className="flex min-h-[40vh] flex-col items-center justify-center text-center">
          <div className="mb-6 rounded-3xl border border-dark-border bg-dark-card p-8">
            <Library className="mx-auto h-20 w-20 text-status-warning" />
          </div>
          <p className="mb-2 text-2xl font-bold text-text-primary">
            {lang === 'ar'
              ? 'حدث خطأ في تحميل البيانات'
              : 'Failed to load data'}
          </p>
          <p className="mb-6 text-text-secondary">
            {lang === 'ar' ? 'يرجى المحاولة مرة أخرى' : 'Please try again'}
          </p>
          <button
            onClick={fetchItems}
            className="inline-flex items-center gap-2 rounded-xl border border-status-star/30 bg-status-star/10 px-6 py-3 font-medium text-status-star transition-all hover:bg-status-star/20"
          >
            {lang === 'ar' ? 'إعادة المحاولة' : 'Retry'}
          </button>
        </div>
      )}

      {/* ---- Empty state ---- */}
      {!loading && !error && filteredItems.length === 0 && (
        <div className="flex min-h-[40vh] flex-col items-center justify-center text-center">
          <div className="mb-6 rounded-3xl border border-dark-border bg-dark-card p-8">
            <BookOpen className="mx-auto h-20 w-20 text-status-star" />
          </div>
          <p className="mb-2 text-2xl font-bold text-text-primary">
            {activeType === 'ALL'
              ? lang === 'ar'
                ? 'لا توجد عناصر في الأرشيف بعد'
                : 'No archive items yet'
              : lang === 'ar'
                ? `لا توجد عناصر من نوع "${TYPE_LABELS[activeType][lang]}"`
                : `No items of type "${TYPE_LABELS[activeType][lang]}"`}
          </p>
          <p className="mb-6 text-text-secondary">
            {lang === 'ar'
              ? 'سيتم إضافة محتوى قريباً'
              : 'Content will be added soon'}
          </p>
          {activeType !== 'ALL' && (
            <button
              onClick={() => setActiveType('ALL')}
              className="inline-flex items-center gap-2 rounded-xl border border-status-star/30 bg-status-star/10 px-6 py-3 font-medium text-status-star transition-all hover:bg-status-star/20"
            >
              {lang === 'ar' ? 'عرض الكل' : 'Show All'}
            </button>
          )}
        </div>
      )}

      {/* ---- Items grid ---- */}
      {!loading && !error && filteredItems.length > 0 && (
        <>
          <p className="mb-4 text-sm text-text-muted">
            {lang === 'ar'
              ? `عرض ${filteredItems.length} عنصر`
              : `Showing ${filteredItems.length} item${filteredItems.length !== 1 ? 's' : ''}`}
          </p>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredItems.map((item) => (
              <ArchiveCard key={item.id} item={item} lang={lang} />
            ))}
          </div>
        </>
      )}
    </main>
  )
}
