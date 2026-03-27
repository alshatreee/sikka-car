'use client'

import { useState, useTransition } from 'react'
import { submitCarListing } from '@/actions/carActions'
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

export default function ListPage() {
  const { t, lang } = useLanguage()
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [images, setImages] = useState<string[]>([])
  const [documentImages, setDocumentImages] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  async function handleFileUpload(
    files: FileList | null,
    target: 'images' | 'documents'
  ) {
    if (!files) return
    setUploading(true)

    const uploaded = await Promise.all(
      Array.from(files).map((file) =>
        uploadToCloudinary(
          file,
          target === 'images' ? 'sikka_cars_images' : 'sikka_cars_documents'
        )
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
    setSuccess(false)

    if (images.length === 0) {
      setError(lang === 'ar' ? 'يرجى رفع صورة واحدة على الأقل للسيارة' : 'Please upload at least one car image')
      return
    }

    if (documentImages.length === 0) {
      setError(lang === 'ar' ? 'يرجى رفع صورة واحدة على الأقل للمستندات' : 'Please upload at least one document image')
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

      const result = await submitCarListing(payload)

      if (result.success) {
        setSuccess(true)
        setTimeout(() => router.push('/dashboard'), 2000)
      } else {
        setError(
          lang === 'ar'
            ? 'حدث خطأ في إرسال البيانات. يرجى التحقق من جميع الحقول.'
            : 'Error submitting data. Please check all fields.'
        )
      }
    })
  }

  if (success) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center bg-gray-50">
        <CheckCircle className="mb-4 h-16 w-16 text-status-success" />
        <h2 className="mb-2 text-2xl font-bold text-gray-900">
          {lang === 'ar' ? 'تم إرسال سيارتك بنجاح!' : 'Your car has been submitted!'}
        </h2>
        <p className="text-gray-500">
          {lang === 'ar'
            ? 'سيتم مراجعتها من قبل الإدارة قريباً'
            : 'It will be reviewed by our team shortly'}
        </p>
      </div>
    )
  }

  return (
    <main className="container py-8 pb-24 bg-gray-50 md:pb-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white shadow-lg border border-gray-200">
            <Car className="h-8 w-8 text-brand-solid" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-gray-900">
            {t('listCar')}
          </h1>
          <p className="text-gray-500">
            {lang === 'ar'
              ? 'أضف تفاصيل سيارتك وسنراجعها خلال 24 ساعة'
              : 'Add your car details and we will review within 24 hours'}
          </p>
        </div>

        <form action={onSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="card-light">
            <h2 className="mb-4 text-lg font-bold text-gray-900">
              {lang === 'ar' ? 'المعلومات الأساسية' : 'Basic Information'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  {t('carName')} *
                </label>
                <input
                  name="title"
                  required
                  placeholder={lang === 'ar' ? 'مثال: تويوتا كامري 2024' : 'e.g. Toyota Camry 2024'}
                  className="input-field"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('year')} *
                  </label>
                  <input
                    name="year"
                    type="number"
                    required
                    min="2000"
                    max="2100"
                    placeholder="2024"
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('dailyPrice')} (د.ك) *
                  </label>
                  <input
                    name="dailyPrice"
                    type="number"
                    required
                    step="0.5"
                    min="1"
                    placeholder="15"
                    className="input-field"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('area')} *
                  </label>
                  <select name="area" required className="input-field">
                    <option value="">{t('allAreas')}</option>
                    <option value="العاصمة">العاصمة</option>
                    <option value="حولي">حولي</option>
                    <option value="الفروانية">الفروانية</option>
                    <option value="الأحمدي">الأحمدي</option>
                    <option value="مبارك الكبير">مبارك الكبير</option>
                    <option value="الجهراء">الجهراء</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('city')}
                  </label>
                  <input name="city" placeholder={t('city')} className="input-field" />
                </div>
              </div>
            </div>
          </div>

          {/* Car Details */}
          <div className="card-light">
            <h2 className="mb-4 text-lg font-bold text-gray-900">
              {lang === 'ar' ? 'تفاصيل السيارة' : 'Car Details'}
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('origin')}
                  </label>
                  <input name="origin" placeholder={t('origin')} className="input-field" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('carType')}
                  </label>
                  <input name="type" placeholder={t('carType')} className="input-field" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('category')}
                  </label>
                  <select name="category" className="input-field">
                    <option value="">-- {t('category')} --</option>
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
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('seats')}
                  </label>
                  <input
                    name="seats"
                    type="number"
                    min="1"
                    max="15"
                    placeholder="5"
                    className="input-field"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('transmission')}
                  </label>
                  <select name="transmission" className="input-field">
                    <option value="AUTOMATIC">{t('automatic')}</option>
                    <option value="MANUAL">{t('manual')}</option>
                    <option value="ELECTRIC">{t('electric')}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('minAge')}
                  </label>
                  <input
                    name="minAge"
                    type="number"
                    min="18"
                    placeholder="21"
                    className="input-field"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('smokingPolicy')}
                  </label>
                  <select name="smokingPolicy" className="input-field">
                    <option value="ممنوع">{lang === 'ar' ? 'ممنوع' : 'No Smoking'}</option>
                    <option value="مسموح">{lang === 'ar' ? 'مسموح' : 'Allowed'}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {t('distancePolicy')}
                  </label>
                  <input
                    name="distancePolicy"
                    placeholder={lang === 'ar' ? 'مثال: 200 كم/يوم' : 'e.g. 200 km/day'}
                    className="input-field"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  {t('availability')}
                </label>
                <input
                  name="availabilityText"
                  placeholder={lang === 'ar' ? 'مثال: متاح يومياً من 8 صباحاً' : 'e.g. Available daily from 8 AM'}
                  className="input-field"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  {t('notes')}
                </label>
                <textarea
                  name="notes"
                  rows={3}
                  placeholder={t('notes')}
                  className="input-field"
                />
              </div>
            </div>
          </div>

          {/* Images */}
          <div className="card-light">
            <h2 className="mb-4 text-lg font-bold text-gray-900">
              {lang === 'ar' ? 'الصور والمستندات' : 'Images & Documents'}
            </h2>

            <div className="space-y-6">
              {/* Car Images */}
              <div>
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
                  <ImageIcon className="h-4 w-4 text-primary-400" />
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

                  <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-300 transition-colors hover:border-primary-400 hover:bg-primary-50">
                    {uploading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                    ) : (
                      <>
                        <Upload className="mb-1 h-5 w-5 text-gray-400" />
                        <span className="text-[10px] text-gray-400">
                          {lang === 'ar' ? 'رفع صور' : 'Upload'}
                        </span>
                      </>
                    )}
                    <input
                      type="file"
                      multiple
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => handleFileUpload(e.target.files, 'images')}
                    />
                  </label>
                </div>
              </div>

              {/* Document Images */}
              <div>
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
                  <FileText className="h-4 w-4 text-primary-400" />
                  {t('documents')} *
                </label>

                <div className="flex flex-wrap gap-3">
                  {documentImages.map((url) => (
                    <div key={url} className="group relative h-24 w-24 overflow-hidden rounded-xl">
                      <Image src={url} alt="document" fill className="object-cover" />
                      <button
                        type="button"
                        onClick={() => removeImage(url, 'documents')}
                        className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100"
                      >
                        <X className="h-5 w-5 text-white" />
                      </button>
                    </div>
                  ))}

                  <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-300 transition-colors hover:border-primary-400 hover:bg-primary-50">
                    {uploading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                    ) : (
                      <>
                        <Upload className="mb-1 h-5 w-5 text-gray-400" />
                        <span className="text-[10px] text-gray-400">
                          {lang === 'ar' ? 'رفع مستندات' : 'Upload'}
                        </span>
                      </>
                    )}
                    <input
                      type="file"
                      multiple
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => handleFileUpload(e.target.files, 'documents')}
                    />
                  </label>
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-orange-50 p-4 text-sm text-orange-600 border border-orange-200">
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
              t('submitForReview')
            )}
          </button>
        </form>
      </div>
    </main>
  )
}
