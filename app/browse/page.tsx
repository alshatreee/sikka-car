'use client'

import { useEffect, useState, useCallback } from 'react'
import { getApprovedCars } from '@/actions/carActions'
import { CarCard } from '@/components/cars/CarCard'
import { CarFilters } from '@/components/cars/CarFilters'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { ArrowUpDown, Car, Loader2, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react'

type CarType = Awaited<ReturnType<typeof getApprovedCars>>[number]

export default function BrowsePage() {
  const { t, lang } = useLanguage()
  const [cars, setCars] = useState<CarType[]>([])
  const [filteredCars, setFilteredCars] = useState<CarType[]>([])
  const [loading, setLoading] = useState(true)
  const [filterKey, setFilterKey] = useState(0)
  const [sortBy, setSortBy] = useState<'newest' | 'priceLow' | 'priceHigh' | 'year'>('newest')
  const [currentPage, setCurrentPage] = useState(1)
  const [error, setError] = useState(false)

  const CARS_PER_PAGE = 9

  useEffect(() => {
    getApprovedCars()
      .then((data) => {
        setCars(data)
        setFilteredCars(data)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [])

  const sortCars = useCallback((list: CarType[], sort: string) => {
    const sorted = [...list]
    switch (sort) {
      case 'priceLow':
        sorted.sort((a, b) => Number(a.dailyPrice) - Number(b.dailyPrice))
        break
      case 'priceHigh':
        sorted.sort((a, b) => Number(b.dailyPrice) - Number(a.dailyPrice))
        break
      case 'year':
        sorted.sort((a, b) => b.year - a.year)
        break
      default:
        sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    }
    return sorted
  }, [])

  const handleFilter = useCallback(
    (filters: {
      search?: string
      area?: string
      transmission?: string
      category?: string
    }) => {
      let result = [...cars]

      if (filters.search) {
        const q = filters.search.toLowerCase()
        result = result.filter(
          (car) =>
            car.title.toLowerCase().includes(q) ||
            car.brand?.toLowerCase().includes(q) ||
            car.model?.toLowerCase().includes(q)
        )
      }

      if (filters.area) {
        result = result.filter((car) => car.area === filters.area)
      }

      if (filters.transmission) {
        result = result.filter(
          (car) => car.transmission === filters.transmission
        )
      }

      if (filters.category) {
        result = result.filter((car) => car.category === filters.category)
      }

      setFilteredCars(sortCars(result, sortBy))
      setCurrentPage(1)
    },
    [cars, sortBy, sortCars]
  )

  const handleSort = useCallback((sort: 'newest' | 'priceLow' | 'priceHigh' | 'year') => {
    setSortBy(sort)
    setFilteredCars((prev) => sortCars(prev, sort))
  }, [sortCars])

  const handleResetFilters = () => {
    setFilterKey((prev) => prev + 1)
    handleFilter({})
    setFilteredCars(cars)
    setCurrentPage(1)
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-status-star" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <div className="mb-6 rounded-3xl bg-dark-card border border-dark-border p-8">
          <Car className="mx-auto h-20 w-20 text-status-warning" />
        </div>
        <p className="mb-2 text-2xl font-bold text-text-primary">
          {lang === 'ar' ? 'حدث خطأ في تحميل البيانات' : 'Failed to load data'}
        </p>
        <p className="mb-6 text-text-secondary">
          {lang === 'ar' ? 'يرجى المحاولة مرة أخرى' : 'Please try again'}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 rounded-xl bg-status-star/10 border border-status-star/30 px-6 py-3 font-medium text-status-star transition-all hover:bg-status-star/20"
        >
          <RotateCcw className="h-4 w-4" />
          {lang === 'ar' ? 'إعادة المحاولة' : 'Retry'}
        </button>
      </div>
    )
  }

  // Calculate pagination
  const totalPages = Math.ceil(filteredCars.length / CARS_PER_PAGE)
  const startIndex = (currentPage - 1) * CARS_PER_PAGE
  const endIndex = startIndex + CARS_PER_PAGE
  const paginatedCars = filteredCars.slice(startIndex, endIndex)

  // Generate page numbers to display (max 5 buttons)
  const getPageNumbers = () => {
    const pages = []
    const maxButtons = 5
    let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2))
    let endPage = Math.min(totalPages, startPage + maxButtons - 1)

    if (endPage - startPage + 1 < maxButtons) {
      startPage = Math.max(1, endPage - maxButtons + 1)
    }

    for (let i = startPage; i <= endPage; i++) {
      pages.push(i)
    }
    return pages
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      {/* Page Header */}
      <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="mb-2 text-3xl font-bold text-text-primary">{t('browse')}</h1>
            <p className="text-text-secondary">
              {filteredCars.length === 0
                ? t('noResults')
                : `${lang === 'ar' ? 'عرض' : 'Showing'} ${startIndex + 1}-${Math.min(endIndex, filteredCars.length)} ${lang === 'ar' ? 'من' : 'of'} ${filteredCars.length} ${filteredCars.length === 1 ? t('oneCarAvailable') : t('carsAvailable')}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ArrowUpDown className="h-4 w-4 text-text-muted" />
            <select
              value={sortBy}
              onChange={(e) => handleSort(e.target.value as 'newest' | 'priceLow' | 'priceHigh' | 'year')}
              className="rounded-xl border border-dark-border bg-dark-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-dark-border-light"
            >
              <option value="newest">{t('sortNewest')}</option>
              <option value="priceLow">{t('sortPriceLow')}</option>
              <option value="priceHigh">{t('sortPriceHigh')}</option>
              <option value="year">{t('sortYear')}</option>
            </select>
          </div>
        </div>
      </div>

      <CarFilters key={filterKey} onFilter={handleFilter} />

      {filteredCars.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="mb-6 rounded-3xl bg-dark-card border border-dark-border p-8">
            <Car className="mx-auto h-20 w-20 text-status-star" />
          </div>
          <p className="mb-2 text-2xl font-bold text-text-primary">{t('noResultsTitle')}</p>
          <p className="mb-6 text-text-secondary">{t('noResultsHint')}</p>
          <button
            onClick={handleResetFilters}
            className="inline-flex items-center gap-2 rounded-xl bg-status-star/10 border border-status-star/30 px-6 py-3 font-medium text-status-star transition-all hover:bg-status-star/20"
          >
            <RotateCcw className="h-4 w-4" />
            {t('clearFilters')}
          </button>
        </div>
      ) : (
        <>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {paginatedCars.map((car) => (
              <CarCard key={car.id} car={car} />
            ))}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="mt-12 flex flex-col items-center gap-4">
              <div className="flex items-center gap-2">
                {/* Previous Button */}
                <button
                  onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                  disabled={currentPage === 1}
                  className="rounded-lg border border-dark-border bg-dark-card p-2 text-text-secondary transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:enabled:bg-dark-surface"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>

                {/* Page Numbers */}
                {getPageNumbers().map((page) => (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                      currentPage === page
                        ? 'bg-status-star text-dark-bg'
                        : 'border border-dark-border bg-dark-card text-text-secondary hover:bg-dark-surface'
                    }`}
                  >
                    {page}
                  </button>
                ))}

                {/* Next Button */}
                <button
                  onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                  disabled={currentPage === totalPages}
                  className="rounded-lg border border-dark-border bg-dark-card p-2 text-text-secondary transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:enabled:bg-dark-surface"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>

              {/* Page Info */}
              <p className="text-sm text-text-muted">
                {lang === 'ar'
                  ? `صفحة ${currentPage} من ${totalPages}`
                  : `Page ${currentPage} of ${totalPages}`}
              </p>
            </div>
          )}
        </>
      )}
    </main>
  )
}
