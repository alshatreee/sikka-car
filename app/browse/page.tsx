'use client'

import { useEffect, useState, useCallback } from 'react'
import { getApprovedCars } from '@/actions/carActions'
import { CarCard } from '@/components/cars/CarCard'
import { CarFilters } from '@/components/cars/CarFilters'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { Car, Loader2, RotateCcw } from 'lucide-react'

type CarType = Awaited<ReturnType<typeof getApprovedCars>>[number]

export default function BrowsePage() {
  const { t, lang } = useLanguage()
  const [cars, setCars] = useState<CarType[]>([])
  const [filteredCars, setFilteredCars] = useState<CarType[]>([])
  const [loading, setLoading] = useState(true)
  const [filterKey, setFilterKey] = useState(0)

  useEffect(() => {
    getApprovedCars().then((data) => {
      setCars(data)
      setFilteredCars(data)
      setLoading(false)
    })
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

      setFilteredCars(result)
    },
    [cars]
  )

  const handleResetFilters = () => {
    setFilterKey((prev) => prev + 1)
    handleFilter({})
    setFilteredCars(cars)
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-status-star" />
      </div>
    )
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mb-8">
        <h1 className="mb-2 text-3xl font-bold text-text-primary">{t('browse')}</h1>
        <p className="text-text-secondary">
          {filteredCars.length}{' '}
          {filteredCars.length === 1 ? 'سيارة متاحة' : 'سيارة متاحة'}
        </p>
      </div>

      <CarFilters key={filterKey} onFilter={handleFilter} />

      {filteredCars.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="mb-6 rounded-3xl bg-dark-card border border-dark-border p-8">
            <Car className="mx-auto h-20 w-20 text-status-star" />
          </div>
          <p className="mb-2 text-2xl font-bold text-text-primary">لم يتم العثور على نتائج</p>
          <p className="mb-6 text-text-secondary">جرّب تغيير معايير البحث</p>
          <button
            onClick={handleResetFilters}
            className="inline-flex items-center gap-2 rounded-xl bg-status-star/10 border border-status-star/30 px-6 py-3 font-medium text-status-star transition-all hover:bg-status-star/20"
          >
            <RotateCcw className="h-4 w-4" />
            امسح الفلاتر
          </button>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {filteredCars.map((car) => (
            <CarCard key={car.id} car={car} />
          ))}
        </div>
      )}
    </main>
  )
}
