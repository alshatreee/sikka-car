'use client'

import { useLanguage } from '@/components/shared/LanguageProvider'
import { useState, useTransition } from 'react'
import { createInspection } from '@/actions/inspectionActions'
import { uploadToCloudinary } from '@/utils/uploadImage'
import Image from 'next/image'
import {
  Upload,
  CheckCircle,
  AlertCircle,
  Car,
  Fuel,
  Gauge,
  X,
} from 'lucide-react'

const INSPECTION_ANGLES = [
  { key: 'front', ar: 'الأمام', en: 'Front' },
  { key: 'back', ar: 'الخلف', en: 'Back' },
  { key: 'right', ar: 'الجانب الأيمن', en: 'Right Side' },
  { key: 'left', ar: 'الجانب الأيسر', en: 'Left Side' },
  { key: 'interior', ar: 'الداخل', en: 'Interior' },
  { key: 'odometer', ar: 'عداد المسافات', en: 'Odometer' },
]

const FUEL_LEVELS = [
  { value: 'FULL', ar: 'ممتلئ', en: 'Full' },
  { value: '3/4', ar: '3/4', en: '3/4' },
  { value: '1/2', ar: '1/2', en: '1/2' },
  { value: '1/4', ar: '1/4', en: '1/4' },
  { value: 'EMPTY', ar: 'فارغ', en: 'Empty' },
]

interface InspectionClientProps {
  booking: {
    id: string
    status: string
    startDate: Date
    endDate: Date
    car: {
      id: string
      title: string
      ownerId: string
      images: string[]
    }
    renter: {
      id: string
      fullName: string | null
      email: string
    }
    inspections: Array<{
      id: string
      type: string
      photos: string[]
      notes: string | null
      mileage: number | null
      fuelLevel: string | null
      createdAt: Date
    }>
  }
}

export default function InspectionClient({ booking }: InspectionClientProps) {
  const { t, lang } = useLanguage()
  const [isPending, startTransition] = useTransition()
  const [uploadingAngle, setUploadingAngle] = useState<string | null>(null)
  const [photos, setPhotos] = useState<Record<string, string>>({})
  const [mileage, setMileage] = useState('')
  const [fuelLevel, setFuelLevel] = useState('FULL')
  const [notes, setNotes] = useState('')
  const [inspectionType, setInspectionType] = useState<'PICKUP' | 'RETURN'>('PICKUP')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const requiredPhotos = INSPECTION_ANGLES.length
  const uploadedPhotos = Object.keys(photos).length

  const existingPickupInspection = booking.inspections.find((i) => i.type === 'PICKUP')
  const existingReturnInspection = booking.inspections.find((i) => i.type === 'RETURN')

  const canAddPickup = booking.status === 'ACTIVE' || booking.status === 'APPROVED'
  const canAddReturn = booking.status === 'ACTIVE' || booking.status === 'COMPLETED'

  async function handlePhotoUpload(angle: string, file: File) {
    setUploadingAngle(angle)
    try {
      const url = await uploadToCloudinary(file)
      if (url) {
        setPhotos((prev) => ({ ...prev, [angle]: url }))
        setError('')
      } else {
        setError(
          lang === 'ar'
            ? 'فشل رفع الصورة'
            : 'Failed to upload photo'
        )
      }
    } catch (err) {
      setError(
        lang === 'ar'
          ? 'خطأ في رفع الصورة'
          : 'Error uploading photo'
      )
    } finally {
      setUploadingAngle(null)
    }
  }

  function removePhoto(angle: string) {
    setPhotos((prev) => {
      const newPhotos = { ...prev }
      delete newPhotos[angle]
      return newPhotos
    })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess(false)

    // Validate
    const photoArray = Object.values(photos)
    if (photoArray.length < requiredPhotos) {
      setError(
        lang === 'ar'
          ? `يجب إضافة جميع ${requiredPhotos} صور`
          : `All ${requiredPhotos} photos are required`
      )
      return
    }

    if (!mileage || isNaN(parseInt(mileage))) {
      setError(
        lang === 'ar' ? 'أدخل قراءة عداد المسافات' : 'Please enter mileage'
      )
      return
    }

    if (!fuelLevel) {
      setError(
        lang === 'ar' ? 'اختر مستوى الوقود' : 'Please select fuel level'
      )
      return
    }

    startTransition(async () => {
      const result = await createInspection(
        booking.id,
        inspectionType,
        photoArray,
        notes || undefined,
        parseInt(mileage),
        fuelLevel
      )

      if (result.success) {
        setSuccess(true)
        setPhotos({})
        setMileage('')
        setFuelLevel('FULL')
        setNotes('')
        setTimeout(() => setSuccess(false), 3000)
      } else {
        setError(result.error || 'حدث خطأ ما')
      }
    })
  }

  const formatDate = (date: Date) =>
    new Date(date).toLocaleDateString(lang === 'ar' ? 'ar-KW' : 'en-US')

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-text-primary mb-2">
            {lang === 'ar' ? 'توثيق الفحص' : 'Inspection Documentation'}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar'
              ? 'التقط صور تفصيلية للسيارة مع تدوين حالتها'
              : 'Take detailed photos of the car and document its condition'}
          </p>
        </div>

        {/* Booking Info Card */}
        <div className="card mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-text-secondary mb-1">
                {lang === 'ar' ? 'السيارة' : 'Car'}
              </p>
              <p className="font-bold text-text-primary">{booking.car.title}</p>
            </div>
            <div>
              <p className="text-sm text-text-secondary mb-1">
                {lang === 'ar' ? 'فترة الإيجار' : 'Rental Period'}
              </p>
              <p className="font-bold text-text-primary">
                {formatDate(booking.startDate)} → {formatDate(booking.endDate)}
              </p>
            </div>
          </div>
        </div>

        {/* Existing Inspections */}
        {booking.inspections.length > 0 && (
          <div className="card mb-6 border border-dark-border">
            <h2 className="font-bold text-text-primary mb-4">
              {lang === 'ar' ? 'الفحوصات السابقة' : 'Previous Inspections'}
            </h2>
            <div className="space-y-4">
              {booking.inspections.map((inspection) => (
                <div
                  key={inspection.id}
                  className="rounded-lg bg-dark-surface p-4 border border-dark-border"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-text-primary">
                        {inspection.type === 'PICKUP'
                          ? lang === 'ar'
                            ? 'فحص الاستلام'
                            : 'Pickup Inspection'
                          : lang === 'ar'
                            ? 'فحص الإرجاع'
                            : 'Return Inspection'}
                      </p>
                      <p className="text-xs text-text-secondary">
                        {new Date(inspection.createdAt).toLocaleDateString(
                          lang === 'ar' ? 'ar-KW' : 'en-US'
                        )}
                      </p>
                    </div>
                    <CheckCircle className="h-5 w-5 text-status-success flex-shrink-0" />
                  </div>

                  {/* Photo Grid */}
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {inspection.photos.map((photo, idx) => (
                      <div
                        key={idx}
                        className="relative h-16 rounded-lg overflow-hidden bg-dark-card"
                      >
                        <Image
                          src={photo}
                          alt={`Inspection photo ${idx + 1}`}
                          fill
                          className="object-cover"
                        />
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {inspection.mileage && (
                      <div className="flex items-center gap-1 text-text-secondary">
                        <Gauge className="h-3 w-3" />
                        {inspection.mileage} km
                      </div>
                    )}
                    {inspection.fuelLevel && (
                      <div className="flex items-center gap-1 text-text-secondary">
                        <Fuel className="h-3 w-3" />
                        {inspection.fuelLevel}
                      </div>
                    )}
                  </div>

                  {inspection.notes && (
                    <p className="text-xs text-text-secondary mt-2 italic">
                      "{inspection.notes}"
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Inspection Form */}
        {(!existingPickupInspection || !existingReturnInspection) && (
          <form onSubmit={handleSubmit} className="card">
            {/* Type Selector */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-text-primary mb-3">
                {lang === 'ar' ? 'نوع الفحص' : 'Inspection Type'}
              </label>
              <div className="flex gap-3">
                {!existingPickupInspection && (
                  <button
                    type="button"
                    onClick={() => setInspectionType('PICKUP')}
                    className={`flex-1 rounded-lg border-2 px-4 py-2 font-medium transition-colors ${
                      inspectionType === 'PICKUP'
                        ? 'border-status-success bg-status-success/10 text-status-success'
                        : 'border-dark-border bg-dark-surface text-text-secondary hover:border-dark-border-light'
                    } ${!canAddPickup ? 'opacity-50 cursor-not-allowed' : ''}`}
                    disabled={!canAddPickup}
                  >
                    {lang === 'ar' ? 'فحص الاستلام' : 'Pickup Inspection'}
                  </button>
                )}
                {!existingReturnInspection && (
                  <button
                    type="button"
                    onClick={() => setInspectionType('RETURN')}
                    className={`flex-1 rounded-lg border-2 px-4 py-2 font-medium transition-colors ${
                      inspectionType === 'RETURN'
                        ? 'border-status-success bg-status-success/10 text-status-success'
                        : 'border-dark-border bg-dark-surface text-text-secondary hover:border-dark-border-light'
                    } ${!canAddReturn ? 'opacity-50 cursor-not-allowed' : ''}`}
                    disabled={!canAddReturn}
                  >
                    {lang === 'ar' ? 'فحص الإرجاع' : 'Return Inspection'}
                  </button>
                )}
              </div>
              {existingPickupInspection && existingReturnInspection && (
                <p className="text-sm text-status-success mt-3">
                  {lang === 'ar'
                    ? 'تم إكمال جميع الفحوصات المطلوبة'
                    : 'All inspections completed'}
                </p>
              )}
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-6 flex items-center gap-3 rounded-lg border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-400">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Success Message */}
            {success && (
              <div className="mb-6 flex items-center gap-3 rounded-lg border border-status-success/20 bg-status-success/10 p-3 text-sm text-status-success">
                <CheckCircle className="h-4 w-4 flex-shrink-0" />
                {lang === 'ar' ? 'تم حفظ الفحص بنجاح' : 'Inspection saved successfully'}
              </div>
            )}

            {/* Photo Checklist */}
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <label className="block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'الصور المطلوبة' : 'Required Photos'}
                </label>
                <span className="text-xs text-text-secondary">
                  {uploadedPhotos}/{requiredPhotos}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {INSPECTION_ANGLES.map((angle) => {
                  const hasPhoto = photos[angle.key]
                  return (
                    <div key={angle.key} className="relative">
                      {hasPhoto ? (
                        <div className="relative h-32 rounded-lg overflow-hidden border-2 border-status-success/20 bg-dark-surface">
                          <Image
                            src={hasPhoto}
                            alt={angle[lang as 'ar' | 'en']}
                            fill
                            className="object-cover"
                          />
                          <button
                            type="button"
                            onClick={() => removePhoto(angle.key)}
                            className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 hover:opacity-100 transition-opacity"
                          >
                            <X className="h-6 w-6 text-white" />
                          </button>
                          <div className="absolute bottom-1 left-1 flex items-center gap-1 rounded bg-status-success/20 px-2 py-1 text-xs font-medium text-status-success border border-status-success/20">
                            <CheckCircle className="h-3 w-3" />
                          </div>
                        </div>
                      ) : (
                        <label className="relative h-32 rounded-lg border-2 border-dashed border-dark-border bg-dark-surface hover:border-dark-border-light cursor-pointer transition-colors flex items-center justify-center group">
                          <input
                            type="file"
                            accept="image/*"
                            onChange={(e) => {
                              const file = e.target.files?.[0]
                              if (file) {
                                handlePhotoUpload(angle.key, file)
                              }
                            }}
                            disabled={uploadingAngle === angle.key}
                            className="hidden"
                          />
                          <div className="text-center">
                            <Upload
                              className={`h-5 w-5 mx-auto mb-1 ${
                                uploadingAngle === angle.key
                                  ? 'animate-pulse text-status-star'
                                  : 'text-text-secondary group-hover:text-text-primary'
                              }`}
                            />
                            <p className="text-xs text-text-secondary group-hover:text-text-primary">
                              {uploadingAngle === angle.key
                                ? lang === 'ar'
                                  ? 'جاري الرفع...'
                                  : 'Uploading...'
                                : angle[lang as 'ar' | 'en']}
                            </p>
                          </div>
                        </label>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Mileage Input */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-text-primary mb-2">
                {lang === 'ar' ? 'عداد المسافات (كم)' : 'Mileage (km)'}
              </label>
              <div className="relative">
                <Gauge className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-text-secondary pointer-events-none" />
                <input
                  type="number"
                  value={mileage}
                  onChange={(e) => setMileage(e.target.value)}
                  placeholder={lang === 'ar' ? 'أدخل قراءة العداد' : 'Enter mileage'}
                  className="w-full rounded-lg border border-dark-border bg-dark-card py-2 pr-10 pl-3 text-text-primary outline-none placeholder:text-text-muted focus:border-dark-border-light"
                />
              </div>
            </div>

            {/* Fuel Level Select */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-text-primary mb-2">
                {lang === 'ar' ? 'مستوى الوقود' : 'Fuel Level'}
              </label>
              <div className="relative">
                <Fuel className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-text-secondary pointer-events-none" />
                <select
                  value={fuelLevel}
                  onChange={(e) => setFuelLevel(e.target.value)}
                  className="w-full rounded-lg border border-dark-border bg-dark-card py-2 pr-10 pl-3 text-text-primary outline-none focus:border-dark-border-light appearance-none"
                >
                  {FUEL_LEVELS.map((level) => (
                    <option key={level.value} value={level.value}>
                      {level[lang as 'ar' | 'en']}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Notes Textarea */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-text-primary mb-2">
                {lang === 'ar' ? 'ملاحظات إضافية' : 'Additional Notes'}
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={lang === 'ar'
                  ? 'أضف أي ملاحظات عن حالة السيارة...'
                  : 'Add any notes about the car condition...'}
                rows={4}
                className="w-full rounded-lg border border-dark-border bg-dark-card p-3 text-text-primary outline-none placeholder:text-text-muted focus:border-dark-border-light resize-none"
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={
                isPending ||
                uploadedPhotos < requiredPhotos ||
                !mileage ||
                !fuelLevel
              }
              className="w-full rounded-lg bg-status-success px-4 py-2.5 font-medium text-dark-bg hover:bg-status-success/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending
                ? lang === 'ar'
                  ? 'جاري الحفظ...'
                  : 'Saving...'
                : lang === 'ar'
                  ? 'حفظ الفحص'
                  : 'Save Inspection'}
            </button>
          </form>
        )}

        {existingPickupInspection && existingReturnInspection && (
          <div className="card bg-status-success/5 border border-status-success/20">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-6 w-6 text-status-success flex-shrink-0" />
              <div>
                <p className="font-medium text-status-success">
                  {lang === 'ar'
                    ? 'تم إكمال جميع الفحوصات'
                    : 'All inspections completed'}
                </p>
                <p className="text-sm text-status-success/80">
                  {lang === 'ar'
                    ? 'تم توثيق الاستلام والإرجاع بنجاح'
                    : 'Pickup and return have been documented'}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
