'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'

interface CarFiltersProps {
  onFilter: (filters: {
    search?: string
    area?: string
    transmission?: string
    category?: string
  }) => void
}

const areas = [
  { value: 'العاصمة', en: 'Capital' },
  { value: 'حولي', en: 'Hawalli' },
  { value: 'الفروانية', en: 'Farwaniya' },
  { value: 'الأحمدي', en: 'Ahmadi' },
  { value: 'مبارك الكبير', en: 'Mubarak Al-Kabeer' },
  { value: 'الجهراء', en: 'Jahra' },
]

const categories = [
  { value: 'سيدان', en: 'Sedan' },
  { value: 'SUV', en: 'SUV' },
  { value: 'كوبيه', en: 'Coupe' },
  { value: 'بيك أب', en: 'Pickup' },
  { value: 'فان', en: 'Van' },
  { value: 'رياضية', en: 'Sport' },
  { value: 'كلاسيك', en: 'Classic' },
]

export function CarFilters({ onFilter }: CarFiltersProps) {
  const { t, lang } = useLanguage()
  const [search, setSearch] = useState('')
  const [area, setArea] = useState('')
  const [transmission, setTransmission] = useState('')
  const [category, setCategory] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  function handleSearch(value: string) {
    setSearch(value)
    onFilter({ search: value, area, transmission, category })
  }

  function handleFilter(updates: Record<string, string>) {
    const newFilters = { search, area, transmission, category, ...updates }
    if ('area' in updates) setArea(updates.area)
    if ('transmission' in updates) setTransmission(updates.transmission)
    if ('category' in updates) setCategory(updates.category)
    onFilter(newFilters)
  }

  function resetFilters() {
    setSearch('')
    setArea('')
    setTransmission('')
    setCategory('')
    onFilter({})
  }

  const hasActiveFilters = search || area || transmission || category

  return (
    <div className="mb-8 space-y-4">
      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={t('search')}
          className="w-full rounded-2xl border border-dark-border bg-dark-card py-3.5 pe-4 ps-12 text-text-primary shadow-sm outline-none transition-all placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
        />
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`absolute end-3 top-1/2 -translate-y-1/2 rounded-xl p-2 transition-colors ${
            showFilters ? 'bg-status-star text-dark-bg' : 'bg-dark-surface text-text-secondary hover:bg-dark-border'
          }`}
        >
          <SlidersHorizontal className="h-4 w-4" />
        </button>
      </div>

      {/* Filter Chips */}
      {showFilters && (
        <div className="space-y-4 rounded-2xl border border-dark-border bg-dark-card p-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-text-primary">
              {lang === 'ar' ? 'المحافظة' : 'Governorate'}
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleFilter({ area: '' })}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  !area
                    ? 'bg-status-star text-dark-bg'
                    : 'border border-dark-border-light bg-dark-surface text-text-secondary hover:bg-dark-border'
                }`}
              >
                {t('allAreas')}
              </button>
              {areas.map((a) => (
                <button
                  key={a.value}
                  onClick={() => handleFilter({ area: a.value })}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    area === a.value
                      ? 'bg-status-star text-dark-bg'
                      : 'border border-dark-border-light bg-dark-surface text-text-secondary hover:bg-dark-border'
                  }`}
                >
                  {lang === 'ar' ? a.value : a.en}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-text-primary">
              {t('transmission')}
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleFilter({ transmission: '' })}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  !transmission
                    ? 'bg-status-star text-dark-bg'
                    : 'border border-dark-border-light bg-dark-surface text-text-secondary hover:bg-dark-border'
                }`}
              >
                {t('allTransmissions')}
              </button>
              {[
                { value: 'AUTOMATIC', label: t('automatic') },
                { value: 'MANUAL', label: t('manual') },
                { value: 'ELECTRIC', label: t('electric') },
              ].map((item) => (
                <button
                  key={item.value}
                  onClick={() => handleFilter({ transmission: item.value })}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    transmission === item.value
                      ? 'bg-status-star text-dark-bg'
                      : 'border border-dark-border-light bg-dark-surface text-text-secondary hover:bg-dark-border'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-text-primary">
              {t('category')}
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleFilter({ category: '' })}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  !category
                    ? 'bg-status-star text-dark-bg'
                    : 'border border-dark-border-light bg-dark-surface text-text-secondary hover:bg-dark-border'
                }`}
              >
                {t('allCategories')}
              </button>
              {categories.map((c) => (
                <button
                  key={c.value}
                  onClick={() => handleFilter({ category: c.value })}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    category === c.value
                      ? 'bg-status-star text-dark-bg'
                      : 'border border-dark-border-light bg-dark-surface text-text-secondary hover:bg-dark-border'
                  }`}
                >
                  {lang === 'ar' ? c.value : c.en}
                </button>
              ))}
            </div>
          </div>

          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="flex items-center gap-1 text-sm text-status-warning hover:text-orange-500"
            >
              <X className="h-4 w-4" />
              {t('reset')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
