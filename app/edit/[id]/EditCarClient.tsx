'use client'

import { useState, useTransition } from 'react'
import { updateCarListing } from '@/actions/carActions'
import { uploadToCloudinary } from '@/utils/uploadImage'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { useRouter } from 'next/navigation'
import {
  Upload,
  X,
  Car,
  CheckCircle,
  AlertCircle,
  Loader2,
  ImageIcon,
  FileText,
} from 'lucide-react'
import Image from 'next/image'

interface EditCarClientProps {
  car: {
    id: string
    title: string
    year: number
    dailyPrice: string
    area: string
    city?: string | null
    origin?: string | null
    type?: string | null
    category?: string | null
    seats?: number | null
    transmission?: string | null
    smokingPolicy?: string | null
    distancePolicy?: string | null
    minAge?: number | null
    availabilityText?: string | null
    notes?: string | null
    images: string[]
    documentImages: string[]
  }
}

export default function EditCarClient({ car }: EditCarClientProps) {
  const { t, lang } = useLanguage()
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [images, setImages] = useState<string[]>(car.images)
  const [documentImages, setDocumentImages] = useState<string[]>(car.documentImages)
  const [uploading, setUploading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  async function handleFileUpload(files: FileList | null, target: 'images' | 'documents') {
    if (!files) return
    setUploading(true)
    const uploaded = await Promise.all(
      Array.from(files).map((file) =>
        uploadToCloudinary(file, target === 'images' ? 'sikka_cars_images' : 'sikka_cars_documents')
      )
    )
    const validUrls = uploaded.filter(Boolean) as string[]
    if (target === 'images') setImages((prev) => [...prev, ...validUrls])
    else setDocumentImages((prev) => [...prev, ...validUrls])
    setUploading(false)
  }

  function removeImage(url: string, target: 'images' | 'documents') {
    if (target === 'images') setImages((prev) => prev.filter((u) => u !== url))
    else setDocumentImages((prev) => prev.filter((u) => u !== url))
  }

  function onSubmit(formData: FormData) {
    setError('')
    if (images.length === 0) {
      setError(lang === 'ar' ? 'يرجى رفع صورة واحدة على الأقل' : 'Please upload at least one image')
      return
    }
    if (documentImages.length === 0) {
      setError(lang === 'ar' ? 'يرجى رفع مستند واحد على الأقل' : 'Please upload at least one document')
      return
    }

    startTransition(async () => {
      const payload = {
        title: formData.get('title'),
        year: formData.get('year'),
        dailyPrice: formData.get('dailyPrice'),
        area: formData.get('area'),
        city: formData.get('city'),
        origin: formData.get('origin'),
        type: formData.get('type'),
        category: formData.get('category'),
        seats: formData.get('seats'),
        transmission: formData.get('transmission'),
        smokingPolicy: formData.get('smokingPolicy'),
        distancePolicy: formData.get('distancePolicy'),
        minAge: formData.get('minAge'),
        availabilityText: formData.get('availabilityText'),
        notes: formData.get('notes'),
        images,
        documentImages,
      }

      const result = await updateCarListing(car.id, payload)
      if (result.success) {
        setSuccess(true)
        setTimeout(() => router.push('/dashboard'), 2000)
      } else {
        setError(lang === 'ar' ? 'حدث خطأ في تحديث البيانات' : 'Error updating car')
      }
    })
  }

  if (success) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center">
        <CheckCircle className="mb-4 h-16 w-16 text-status-success" />
        <h2 className="mb-2 text-2xl font-bold text-text-primary">
          {lang === 'ar' ? 'تم تحديث السيارة بنجاح!' : 'Car updated successfully!'}
        </h2>
        <p className="text-text-secondary">
          {lang === 'ar' ? 'سيتم مراجعتها من قبل الإدارة' : 'It will be reviewed by our team'}
        </p>
      </div>
    )
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-card border border-dark-border">
            <Car className="h-8 w-8 text-status-star" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'تعديل السيارة' : 'Edit Car'}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar' ? 'عدّل بيانات سيارتك وسيتم مراجعتها مجدداً' : 'Update your car details for re-review'}
          </p>
        </div>

        <form action={onSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="card">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'المعلومات الأساسية' : 'Basic Information'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-text-secondary">{t('carName')} *</label>
                <input name="title" required defaultValue={car.title} className="input-field" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('year')} *</label>
                  <input name="year" type="number" required defaultValue={car.year} className="input-field" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('dailyPrice')} ({lang === 'ar' ? 'د.ك' : 'KWD'}) *</label>
                  <input name="dailyPrice" type="number" required step="0.5" defaultValue={car.dailyPrice} className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('area')} *</label>
                  <select name="area" required defaultValue={car.area} className="input-field">
                    <option value="العاصمة">العاصمة</option>
                    <option value="حولي">حولي</option>
                    <option value="الفروانية">الفروانية</option>
                    <option value="الأحمدي">الأحمدي</option>
                    <option value="مبارك الكبير">مبارك الكبير</option>
                    <option value="الجهراء">الجهراء</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('city')}</label>
                  <input name="city" defaultValue={car.city || ''} className="input-field" />
                </div>
              </div>
            </div>
          </div>

          {/* Car Details */}
          <div className="card">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'تفاصيل السيارة' : 'Car Details'}
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('origin')}</label>
                  <input name="origin" defaultValue={car.origin || ''} className="input-field" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('carType')}</label>
                  <input name="type" defaultValue={car.type || ''} className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('category')}</label>
                  <select name="category" defaultValue={car.category || ''} className="input-field">
                    <option value="">--</option>
                    <option value="سيدان">سيدان</option>
                    <option value="SUV">SUV</option>
                    <option value="كوبيه">كوبيه</option>
                    <option value="بيك أب">بيك أب</option>
                    <option value="فان">فان</option>
                    <option value="رياضية">رياضية</option>
                    <option value="كلاسيك">كلاسيك</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('seats')}</label>
                  <input name="seats" type="number" defaultValue={car.seats || ''} className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('transmission')}</label>
                  <select name="transmission" defaultValue={car.transmission || 'AUTOMATIC'} className="input-field">
                    <option value="AUTOMATIC">{t('automatic')}</option>
                    <option value="MANUAL">{t('manual')}</option>
                    <option value="ELECTRIC">{t('electric')}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('minAge')}</label>
                  <input name="minAge" type="number" defaultValue={car.minAge || ''} className="input-field" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('smokingPolicy')}</label>
                  <select name="smokingPolicy" defaultValue={car.smokingPolicy || 'ممنوع'} className="input-field">
                    <option value="ممنوع">{lang === 'ar' ? 'ممنوع' : 'No Smoking'}</option>
                    <option value="مسموح">{lang === 'ar' ? 'مسموح' : 'Allowed'}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-secondary">{t('distancePolicy')}</label>
                  <input name="distancePolicy" defaultValue={car.distancePolicy || ''} className="input-field" />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-text-secondary">{t('availability')}</label>
                <input name="availabilityText" defaultValue={car.availabilityText || ''} className="input-field" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-text-secondary">{t('notes')}</label>
                <textarea name="notes" rows={3} defaultValue={car.notes || ''} className="input-field" />
              </div>
            </div>
          </div>

          {/* Images */}
          <div className="card">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'الصور والمستندات' : 'Images & Documents'}
            </h2>
            <div className="space-y-6">
              <div>
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-text-secondary">
                  <ImageIcon className="h-4 w-4" />
                  {t('carImages')} *
                </label>
                <div className="flex flex-wrap gap-3">
                  {images.map((url) => (
                    <div key={url} className="group relative h-24 w-24 overflow-hidden rounded-xl">
                      <Image src={url} alt="car" fill className="object-cover" />
                      <button
                        type="button"
                        onClick={() => removeImage(url, 'images')}
                        className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100"
                      >
                        <X className="h-5 w-5 text-white" />
                      </button>
                    </div>
                  ))}
                  <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star">
                    {uploading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
                    ) : (
                      <>
                        <Upload className="mb-1 h-5 w-5 text-text-muted" />
                        <span className="text-[10px] text-text-muted">{lang === 'ar' ? 'رفع' : 'Upload'}</span>
                      </>
                    )}
                    <input type="file" multiple accept="image/*" className="hidden" onChange={(e) => handleFileUpload(e.target.files, 'images')} />
                  </label>
                </div>
              </div>
              <div>
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-text-secondary">
                  <FileText className="h-4 w-4" />
                  {t('documents')} *
                </label>
                <div className="flex flex-wrap gap-3">
                  {documentImages.map((url) => (
                    <div key={url} className="group relative h-24 w-24 overflow-hidden rounded-xl">
                      <Image src={url} alt="doc" fill className="object-cover" />
                      <button
                        type="button"
                        onClick={() => removeImage(url, 'documents')}
                        className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100"
                      >
                        <X className="h-5 w-5 text-white" />
                      </button>
                    </div>
                  ))}
                  <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star">
                    {uploading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
                    ) : (
                      <>
                        <Upload className="mb-1 h-5 w-5 text-text-muted" />
                        <span className="text-[10px] text-text-muted">{lang === 'ar' ? 'رفع' : 'Upload'}</span>
                      </>
                    )}
                    <input type="file" multiple accept="image/*" className="hidden" onChange={(e) => handleFileUpload(e.target.files, 'documents')} />
                  </label>
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-red-400/10 p-4 text-sm text-red-400 border border-red-400/20">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={pending || uploading}
            className="btn-solid w-full !py-4 text-lg disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                {t('submitting')}
              </span>
            ) : (
              lang === 'ar' ? 'حفظ التعديلات' : 'Save Changes'
            )}
          </button>
        </form>
      </div>
    </main>
  )
}
