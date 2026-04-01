'use client'

import { useState, useEffect, useCallback, FormEvent } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Search, Filter, X, BookOpen, ArrowRight, Loader2 } from 'lucide-react'

interface SearchResult {
  id: string
  slug: string
  titleAr: string
  titleEn: string | null
  itemType: string
  creator: string | null
  publicationYear: number | null
  thumbnailUrl: string | null
}

const ITEM_TYPES = [
  'ARTICLE',
  'BOOK',
  'MANUSCRIPT',
  'DOCUMENT',
  'IMAGE',
  'AUDIO',
  'VIDEO',
  'PUBLICATION',
] as const

type ArchiveItemType = (typeof ITEM_TYPES)[number]

const itemTypeLabels: Record<ArchiveItemType, { ar: string; en: string }> = {
  ARTICLE: { ar: 'مقال', en: 'Article' },
  BOOK: { ar: 'كتاب', en: 'Book' },
  MANUSCRIPT: { ar: 'مخطوطة', en: 'Manuscript' },
  DOCUMENT: { ar: 'وثيقة', en: 'Document' },
  IMAGE: { ar: 'صورة', en: 'Image' },
  AUDIO: { ar: 'صوتي', en: 'Audio' },
  VIDEO: { ar: 'فيديو', en: 'Video' },
  PUBLICATION: { ar: 'منشور', en: 'Publication' },
}

const itemTypeBadgeColors: Record<ArchiveItemType, string> = {
  ARTICLE: 'bg-blue-500/20 text-blue-400',
  BOOK: 'bg-emerald-500/20 text-emerald-400',
  MANUSCRIPT: 'bg-amber-500/20 text-amber-400',
  DOCUMENT: 'bg-slate-500/20 text-slate-300',
  IMAGE: 'bg-pink-500/20 text-pink-400',
  AUDIO: 'bg-purple-500/20 text-purple-400',
  VIDEO: 'bg-red-500/20 text-red-400',
  PUBLICATION: 'bg-cyan-500/20 text-cyan-400',
}

export default function ArchiveSearchPage() {
  const { lang } = useLanguage()
  const router = useRouter()
  const searchParams = useSearchParams()

  const isAr = lang === 'ar'

  // Form state
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [selectedTypes, setSelectedTypes] = useState<ArchiveItemType[]>(() => {
    const typeParam = searchParams.get('type')
    if (!typeParam) return []
    return typeParam.split(',').filter((t): t is ArchiveItemType =>
      ITEM_TYPES.includes(t as ArchiveItemType)
    )
  })
  const [yearFrom, setYearFrom] = useState(searchParams.get('yearFrom') ?? '')
  const [yearTo, setYearTo] = useState(searchParams.get('yearTo') ?? '')
  const [creator, setCreator] = useState(searchParams.get('creator') ?? '')
  const [showFilters, setShowFilters] = useState(false)

  // Results state
  const [results, setResults] = useState<SearchResult[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const buildSearchUrl = useCallback(() => {
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    if (selectedTypes.length > 0) params.set('type', selectedTypes.join(','))
    if (yearFrom) params.set('yearFrom', yearFrom)
    if (yearTo) params.set('yearTo', yearTo)
    if (creator.trim()) params.set('creator', creator.trim())
    return `/api/archive/search?${params.toString()}`
  }, [query, selectedTypes, yearFrom, yearTo, creator])

  const performSearch = useCallback(async () => {
    setLoading(true)
    setError(null)
    setHasSearched(true)

    try {
      const res = await fetch(buildSearchUrl())
      if (!res.ok) throw new Error('Search failed')
      const data = await res.json()
      setResults(data.results ?? data)
      setTotalCount(data.totalCount ?? (data.results ?? data).length)
    } catch {
      setError(isAr ? 'حدث خطأ أثناء البحث' : 'An error occurred while searching')
      setResults([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }, [buildSearchUrl, isAr])

  // Run search on mount if URL has query params
  useEffect(() => {
    if (searchParams.toString()) {
      performSearch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    if (selectedTypes.length > 0) params.set('type', selectedTypes.join(','))
    if (yearFrom) params.set('yearFrom', yearFrom)
    if (yearTo) params.set('yearTo', yearTo)
    if (creator.trim()) params.set('creator', creator.trim())
    router.replace(`/archive/search?${params.toString()}`, { scroll: false })
    performSearch()
  }

  const toggleType = (type: ArchiveItemType) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    )
  }

  const clearFilters = () => {
    setSelectedTypes([])
    setYearFrom('')
    setYearTo('')
    setCreator('')
  }

  const hasActiveFilters = selectedTypes.length > 0 || yearFrom || yearTo || creator.trim()

  const getTitle = (item: SearchResult) =>
    isAr ? item.titleAr : item.titleEn || item.titleAr

  const getTypeLabel = (type: string) =>
    itemTypeLabels[type as ArchiveItemType]?.[lang] ?? type

  const getTypeBadgeColor = (type: string) =>
    itemTypeBadgeColors[type as ArchiveItemType] ?? 'bg-slate-500/20 text-slate-300'

  return (
    <div className="min-h-screen bg-dark-surface">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Back link */}
        <Link
          href="/archive"
          className="mb-6 inline-flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-text-primary"
        >
          <ArrowRight className={`h-4 w-4 ${isAr ? '' : 'rotate-180'}`} />
          {isAr ? 'العودة إلى الأرشيف' : 'Back to Archive'}
        </Link>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">
            {isAr ? 'البحث في الأرشيف' : 'Search Archive'}
          </h1>
          <p className="mt-2 text-text-muted">
            {isAr
              ? 'ابحث في المقالات والكتب والمخطوطات والوثائق'
              : 'Search through articles, books, manuscripts, and documents'}
          </p>
        </div>

        {/* Search form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Main search input */}
          <div className="relative">
            <Search className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={isAr ? 'ابحث بالعنوان أو الكلمات المفتاحية...' : 'Search by title or keywords...'}
              className="w-full rounded-xl border border-dark-border bg-dark-card py-3.5 pe-4 ps-12 text-text-primary placeholder:text-text-muted focus:border-status-star focus:outline-none focus:ring-1 focus:ring-status-star"
              autoFocus
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute end-4 top-1/2 -translate-y-1/2 text-text-muted transition-colors hover:text-text-primary"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Filter toggle */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="inline-flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              <Filter className="h-4 w-4" />
              {isAr ? 'خيارات البحث المتقدم' : 'Advanced filters'}
              {hasActiveFilters && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-status-star text-xs font-medium text-dark-surface">
                  {selectedTypes.length + (yearFrom ? 1 : 0) + (yearTo ? 1 : 0) + (creator.trim() ? 1 : 0)}
                </span>
              )}
            </button>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-sm text-text-muted transition-colors hover:text-text-primary"
              >
                {isAr ? 'مسح الفلاتر' : 'Clear filters'}
              </button>
            )}
          </div>

          {/* Filters panel */}
          {showFilters && (
            <div className="space-y-5 rounded-xl border border-dark-border bg-dark-card p-5">
              {/* Item type chips */}
              <div>
                <label className="mb-2.5 block text-sm font-medium text-text-secondary">
                  {isAr ? 'نوع المادة' : 'Item Type'}
                </label>
                <div className="flex flex-wrap gap-2">
                  {ITEM_TYPES.map((type) => {
                    const isSelected = selectedTypes.includes(type)
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => toggleType(type)}
                        className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                          isSelected
                            ? 'bg-status-star text-dark-surface'
                            : 'border border-dark-border bg-dark-surface text-text-secondary hover:border-text-muted hover:text-text-primary'
                        }`}
                      >
                        {getTypeLabel(type)}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Year range */}
              <div>
                <label className="mb-2.5 block text-sm font-medium text-text-secondary">
                  {isAr ? 'سنة النشر' : 'Publication Year'}
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={yearFrom}
                    onChange={(e) => setYearFrom(e.target.value)}
                    placeholder={isAr ? 'من' : 'From'}
                    min={1}
                    max={new Date().getFullYear()}
                    className="w-full rounded-lg border border-dark-border bg-dark-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-status-star focus:outline-none focus:ring-1 focus:ring-status-star"
                  />
                  <span className="shrink-0 text-text-muted">—</span>
                  <input
                    type="number"
                    value={yearTo}
                    onChange={(e) => setYearTo(e.target.value)}
                    placeholder={isAr ? 'إلى' : 'To'}
                    min={1}
                    max={new Date().getFullYear()}
                    className="w-full rounded-lg border border-dark-border bg-dark-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-status-star focus:outline-none focus:ring-1 focus:ring-status-star"
                  />
                </div>
              </div>

              {/* Creator */}
              <div>
                <label className="mb-2.5 block text-sm font-medium text-text-secondary">
                  {isAr ? 'المؤلف / المنشئ' : 'Creator / Author'}
                </label>
                <input
                  type="text"
                  value={creator}
                  onChange={(e) => setCreator(e.target.value)}
                  placeholder={isAr ? 'اسم المؤلف أو المنشئ...' : 'Author or creator name...'}
                  className="w-full rounded-lg border border-dark-border bg-dark-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-status-star focus:outline-none focus:ring-1 focus:ring-status-star"
                />
              </div>
            </div>
          )}

          {/* Search button */}
          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-status-star px-6 py-3 font-medium text-dark-surface transition-opacity hover:opacity-90 disabled:opacity-60 sm:w-auto"
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Search className="h-5 w-5" />
            )}
            {isAr ? 'بحث' : 'Search'}
          </button>
        </form>

        {/* Results section */}
        <div className="mt-10">
          {/* Error */}
          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-center text-sm text-red-400">
              {error}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-status-star" />
              <p className="mt-3 text-sm text-text-muted">
                {isAr ? 'جارٍ البحث...' : 'Searching...'}
              </p>
            </div>
          )}

          {/* Results */}
          {!loading && !error && hasSearched && (
            <>
              {/* Result count */}
              <p className="mb-4 text-sm text-text-muted">
                {isAr
                  ? `تم العثور على ${totalCount} نتيجة`
                  : `${totalCount} result${totalCount !== 1 ? 's' : ''} found`}
              </p>

              {results.length > 0 ? (
                <ul className="space-y-3">
                  {results.map((item) => (
                    <li key={item.id}>
                      <Link
                        href={`/archive/item/${item.slug}`}
                        className="group flex items-start gap-4 rounded-xl border border-dark-border bg-dark-card p-4 transition-colors hover:border-status-star/40"
                      >
                        {/* Thumbnail or icon */}
                        {item.thumbnailUrl ? (
                          <img
                            src={item.thumbnailUrl}
                            alt=""
                            className="h-16 w-16 shrink-0 rounded-lg object-cover"
                          />
                        ) : (
                          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-dark-surface">
                            <BookOpen className="h-6 w-6 text-text-muted" />
                          </div>
                        )}

                        {/* Content */}
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-base font-semibold text-text-primary transition-colors group-hover:text-status-star">
                              {getTitle(item)}
                            </h3>
                            <span
                              className={`inline-flex shrink-0 items-center rounded-md px-2 py-0.5 text-xs font-medium ${getTypeBadgeColor(item.itemType)}`}
                            >
                              {getTypeLabel(item.itemType)}
                            </span>
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
                            {item.creator && <span>{item.creator}</span>}
                            {item.creator && item.publicationYear && (
                              <span className="text-text-muted">·</span>
                            )}
                            {item.publicationYear && <span>{item.publicationYear}</span>}
                          </div>
                        </div>

                        {/* Arrow */}
                        <ArrowRight
                          className={`mt-1 h-5 w-5 shrink-0 text-text-muted transition-colors group-hover:text-status-star ${isAr ? 'rotate-180' : ''}`}
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                /* Empty state */
                <div className="flex flex-col items-center justify-center rounded-xl border border-dark-border bg-dark-card py-16">
                  <BookOpen className="h-12 w-12 text-text-muted" />
                  <h3 className="mt-4 text-lg font-semibold text-text-primary">
                    {isAr ? 'لا توجد نتائج' : 'No results found'}
                  </h3>
                  <p className="mt-1 text-sm text-text-muted">
                    {isAr
                      ? 'جرّب تغيير كلمات البحث أو الفلاتر'
                      : 'Try adjusting your search terms or filters'}
                  </p>
                </div>
              )}
            </>
          )}

          {/* Initial state before any search */}
          {!loading && !error && !hasSearched && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Search className="h-12 w-12 text-text-muted" />
              <h3 className="mt-4 text-lg font-semibold text-text-primary">
                {isAr ? 'ابدأ البحث' : 'Start searching'}
              </h3>
              <p className="mt-1 max-w-sm text-sm text-text-muted">
                {isAr
                  ? 'أدخل كلمة بحث أو استخدم الفلاتر للعثور على ما تبحث عنه'
                  : 'Enter a search term or use filters to find what you are looking for'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
