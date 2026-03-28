'use client'

import { useState, useEffect } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { uploadBookingPhoto, getBookingPhotos } from '@/actions/profileActions'
import { uploadToCloudinary } from '@/utils/uploadImage'
import { Camera, Loader2, CheckCircle, Car } from 'lucide-react'
import Image from 'next/image'

interface BookingPhotosProps {
  bookingId: string
  role: 'OWNER' | 'RENTER' | 'ADMIN'
  phase: 'DELIVERY' | 'RETURN'
}

const sides = [
  { key: 'FRONT', ar: 'الأمام', en: 'Front', icon: '⬆️' },
  { key: 'BACK', ar: 'الخلف', en: 'Back', icon: '⬇️' },
  { key: 'LEFT', ar: 'اليسار', en: 'Left', icon: '⬅️' },
  { key: 'RIGHT', ar: 'اليمين', en: 'Right', icon: '➡️' },
]

export function BookingPhotos({ bookingId, role, phase }: BookingPhotosProps) {
  const { lang } = useLanguage()
  const [photos, setPhotos] = useState<Record<string, string>>({})
  const [uploading, setUploading] = useState<string | null>(null)
  const [existingPhotos, setExistingPhotos] = useState<any[]>([])

  useEffect(() => {
    getBookingPhotos(bookingId).then((data) => {
      setExistingPhotos(data)
      const photoMap: Record<string, string> = {}
      data.forEach((p: any) => {
        photoMap[p.type] = p.url
      })
      setPhotos(photoMap)
    })
  }, [bookingId])

  async function handleUpload(file: File, side: string) {
    const type = `${phase}_${side}`
    setUploading(type)

    const url = await uploadToCloudinary(file, 'sikka_booking_photos')
    if (url) {
      await uploadBookingPhoto({
        bookingId,
        url,
        type,
        uploadedBy: role,
      })
      setPhotos((prev) => ({ ...prev, [type]: url }))
    }
    setUploading(null)
  }

  const title = phase === 'DELIVERY'
    ? (lang === 'ar' ? 'تصوير السيارة - التسليم' : 'Car Photos - Delivery')
    : (lang === 'ar' ? 'تصوير السيارة - الإرجاع' : 'Car Photos - Return')

  const subtitle = phase === 'DELIVERY'
    ? (lang === 'ar' ? 'صوّر السيارة من الجهات الأربع قبل التسليم' : 'Photograph the car from all 4 sides before delivery')
    : (lang === 'ar' ? 'صوّر السيارة من الجهات الأربع بعد الإرجاع' : 'Photograph the car from all 4 sides after return')

  return (
    <div className="rounded-2xl border border-dark-border bg-dark-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Camera className="h-5 w-5 text-status-star" />
        <h3 className="font-bold text-text-primary">{title}</h3>
      </div>
      <p className="mb-4 text-xs text-text-secondary">{subtitle}</p>

      <div className="grid grid-cols-2 gap-3">
        {sides.map((side) => {
          const type = `${phase}_${side.key}`
          const photoUrl = photos[type]
          const isUploading = uploading === type

          return (
            <div key={side.key} className="relative">
              <p className="mb-1 text-center text-xs font-medium text-text-secondary">
                {side.icon} {lang === 'ar' ? side.ar : side.en}
              </p>
              {photoUrl ? (
                <div className="relative h-28 w-full overflow-hidden rounded-xl border border-green-500/30">
                  <Image src={photoUrl} alt={side.en} fill className="object-cover" />
                  <div className="absolute bottom-1 end-1 rounded-full bg-green-500/90 p-0.5">
                    <CheckCircle className="h-3.5 w-3.5 text-white" />
                  </div>
                </div>
              ) : (
                <label className="flex h-28 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                  {isUploading ? (
                    <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
                  ) : (
                    <>
                      <Camera className="mb-1 h-6 w-6 text-text-muted" />
                      <span className="text-[10px] text-text-muted">
                        {lang === 'ar' ? 'التقط صورة' : 'Take photo'}
                      </span>
                    </>
                  )}
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) handleUpload(file, side.key)
                    }}
                  />
                </label>
              )}
            </div>
          )
        })}
      </div>

      {Object.keys(photos).filter((k) => k.startsWith(phase)).length === 4 && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-green-500/10 p-2 text-xs text-green-400 border border-green-500/20">
          <CheckCircle className="h-3.5 w-3.5" />
          {lang === 'ar' ? 'تم رفع جميع الصور' : 'All photos uploaded'}
        </div>
      )}
    </div>
  )
}
