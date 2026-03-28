'use client'

import { useState, useTransition, useMemo } from 'react'
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
  const [selectedGovernorate, setSelectedGovernorate] = useState('')

  const governorateCities: Record<string, { value: string; en: string }[]> = {
    'العاصمة': [
      { value: 'الشرق', en: 'Sharq' },
      { value: 'المرقاب', en: 'Mirqab' },
      { value: 'القبلة', en: 'Qibla' },
      { value: 'الدسمة', en: 'Dasma' },
      { value: 'الدعية', en: 'Daiya' },
      { value: 'كيفان', en: 'Kaifan' },
      { value: 'الشامية', en: 'Shamiya' },
      { value: 'الروضة', en: 'Rawda' },
      { value: 'العديلية', en: 'Adailiya' },
      { value: 'الخالدية', en: 'Khalidiya' },
      { value: 'النزهة', en: 'Nuzha' },
      { value: 'الفيحاء', en: 'Faiha' },
      { value: 'القادسية', en: 'Qadsiya' },
      { value: 'قرطبة', en: 'Qurtuba' },
      { value: 'السرة', en: 'Surra' },
      { value: 'اليرموك', en: 'Yarmouk' },
      { value: 'الشويخ', en: 'Shuwaikh' },
    ],
    'حولي': [
      { value: 'حولي', en: 'Hawalli' },
      { value: 'السالمية', en: 'Salmiya' },
      { value: 'الجابرية', en: 'Jabriya' },
      { value: 'الرميثية', en: 'Rumaithiya' },
      { value: 'سلوى', en: 'Salwa' },
      { value: 'بيان', en: 'Bayan' },
      { value: 'مشرف', en: 'Mishref' },
      { value: 'حطين', en: 'Hittin' },
      { value: 'الشهداء', en: 'Shuhada' },
      { value: 'الزهراء', en: 'Zahra' },
    ],
    'الفروانية': [
      { value: 'الفروانية', en: 'Farwaniya' },
      { value: 'خيطان', en: 'Khaitan' },
      { value: 'العمرية', en: 'Omariya' },
      { value: 'الرابية', en: 'Rabiya' },
      { value: 'الأندلس', en: 'Andalus' },
      { value: 'اشبيلية', en: 'Ishbiliya' },
      { value: 'جليب الشيوخ', en: 'Jleeb Al-Shuyoukh' },
      { value: 'الرقعي', en: 'Riggae' },
      { value: 'الحسانية', en: 'Hassaniya' },
      { value: 'عبدالله المبارك', en: 'Abdullah Al-Mubarak' },
    ],
    'الأحمدي': [
      { value: 'الأحمدي', en: 'Ahmadi' },
      { value: 'الفحيحيل', en: 'Fahaheel' },
      { value: 'المنقف', en: 'Mangaf' },
      { value: 'المهبولة', en: 'Mahboula' },
      { value: 'الفنطاس', en: 'Fintas' },
      { value: 'أبو حليفة', en: 'Abu Halifa' },
      { value: 'الرقة', en: 'Riqqa' },
      { value: 'هدية', en: 'Hadiya' },
      { value: 'العقيلة', en: 'Aqeela' },
      { value: 'صباح الأحمد', en: 'Sabah Al-Ahmad' },
    ],
    'مبارك الكبير': [
      { value: 'صباح السالم', en: 'Sabah Al-Salem' },
      { value: 'المسيلة', en: 'Maseela' },
      { value: 'العدان', en: 'Adan' },
      { value: 'القصور', en: 'Qusour' },
      { value: 'القرين', en: 'Qurain' },
      { value: 'الفنيطيس', en: 'Funaitees' },
      { value: 'أبو فطيرة', en: 'Abu Ftaira' },
      { value: 'المسايل', en: 'Masayel' },
    ],
    'الجهراء': [
      { value: 'الجهراء', en: 'Jahra' },
      { value: 'النسيم', en: 'Naseem' },
      { value: 'القصر', en: 'Qasr' },
      { value: 'تيماء', en: 'Taima' },
      { value: 'سعد العبدالله', en: 'Saad Al-Abdullah' },
      { value: 'النعيم', en: 'Naeem' },
      { value: 'العيون', en: 'Oyoun' },
      { value: 'الصليبية', en: 'Sulaibiya' },
    ],
  }

  const availableCities = useMemo(() => {
    return selectedGovernorate ? governorateCities[selectedGovernorate] || [] : []
  }, [selectedGovernorate])

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
      <div className="flex min-h-[60vh] flex-col items-center justify-center">
        <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-green-500/10 border border-green-500/20">
          <CheckCircle className="h-10 w-10 text-green-400" />
        </div>
        <h2 className="mb-2 text-2xl font-bold text-text-primary">
          {lang === 'ar' ? 'تم إرسال سيارتك بنجاح!' : 'Your car has been submitted!'}
        </h2>
        <p className="text-text-secondary">
          {lang === 'ar'
            ? 'سيتم مراجعتها من قبل الإدارة قريباً'
            : 'It will be reviewed by our team shortly'}
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
            {t('listCar')}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar'
              ? 'أضف تفاصيل سيارتك وسنراجعها خلال 24 ساعة'
              : 'Add your car details and we will review within 24 hours'}
          </p>
        </div>

        <form action={onSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'المعلومات الأساسية' : 'Basic Information'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {t('carName')} *
                </label>
                <input
                  name="title"
                  required
                  placeholder={lang === 'ar' ? 'مثال: تويوتا كامري 2024' : 'e.g. Toyota Camry 2024'}
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('year')} *
                  </label>
                  <select name="year" required className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">{lang === 'ar' ? '-- السنة --' : '-- Year --'}</option>
                    {Array.from({ length: 31 }, (_, i) => 2030 - i).map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('dailyPrice')} ({t('kwd')}) *
                  </label>
                  <input
                    name="dailyPrice"
                    type="number"
                    required
                    step="0.5"
                    min="1"
                    placeholder="15"
                    className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'المحافظة' : 'Governorate'} *
                  </label>
                  <select
                    name="area"
                    required
                    value={selectedGovernorate}
                    onChange={(e) => setSelectedGovernorate(e.target.value)}
                    className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                  >
                    <option value="">{lang === 'ar' ? '-- المحافظة --' : '-- Governorate --'}</option>
                    <option value="العاصمة">{lang === 'ar' ? 'العاصمة' : 'Capital'}</option>
                    <option value="حولي">{lang === 'ar' ? 'حولي' : 'Hawalli'}</option>
                    <option value="الفروانية">{lang === 'ar' ? 'الفروانية' : 'Farwaniya'}</option>
                    <option value="الأحمدي">{lang === 'ar' ? 'الأحمدي' : 'Ahmadi'}</option>
                    <option value="مبارك الكبير">{lang === 'ar' ? 'مبارك الكبير' : 'Mubarak Al-Kabeer'}</option>
                    <option value="الجهراء">{lang === 'ar' ? 'الجهراء' : 'Jahra'}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'المنطقة' : 'Area'} *
                  </label>
                  <select
                    name="city"
                    required
                    disabled={!selectedGovernorate}
                    className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="">
                      {!selectedGovernorate
                        ? (lang === 'ar' ? 'اختر المحافظة أولاً' : 'Select governorate first')
                        : (lang === 'ar' ? '-- المنطقة --' : '-- Area --')}
                    </option>
                    {availableCities.map((city) => (
                      <option key={city.value} value={city.value}>
                        {lang === 'ar' ? city.value : city.en}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Car Details */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'تفاصيل السيارة' : 'Car Details'}
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('origin')}
                  </label>
                  <select name="origin" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">{lang === 'ar' ? '-- بلد المنشأ --' : '-- Origin --'}</option>
                    <option value="يابانية">{lang === 'ar' ? 'يابانية' : 'Japanese'}</option>
                    <option value="أمريكية">{lang === 'ar' ? 'أمريكية' : 'American'}</option>
                    <option value="كورية">{lang === 'ar' ? 'كورية' : 'Korean'}</option>
                    <option value="ألمانية">{lang === 'ar' ? 'ألمانية' : 'German'}</option>
                    <option value="بريطانية">{lang === 'ar' ? 'بريطانية' : 'British'}</option>
                    <option value="صينية">{lang === 'ar' ? 'صينية' : 'Chinese'}</option>
                    <option value="أخرى">{lang === 'ar' ? 'أخرى' : 'Other'}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('carType')}
                  </label>
                  <select name="type" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">{lang === 'ar' ? '-- النوع --' : '-- Type --'}</option>
                    <option value="تويوتا">{lang === 'ar' ? 'تويوتا' : 'Toyota'}</option>
                    <option value="نيسان">{lang === 'ar' ? 'نيسان' : 'Nissan'}</option>
                    <option value="هوندا">{lang === 'ar' ? 'هوندا' : 'Honda'}</option>
                    <option value="هيونداي">{lang === 'ar' ? 'هيونداي' : 'Hyundai'}</option>
                    <option value="كيا">{lang === 'ar' ? 'كيا' : 'Kia'}</option>
                    <option value="شيفروليه">{lang === 'ar' ? 'شيفروليه' : 'Chevrolet'}</option>
                    <option value="فورد">{lang === 'ar' ? 'فورد' : 'Ford'}</option>
                    <option value="مرسيدس">{lang === 'ar' ? 'مرسيدس' : 'Mercedes'}</option>
                    <option value="بي ام دبليو">{lang === 'ar' ? 'بي ام دبليو' : 'BMW'}</option>
                    <option value="لكزس">{lang === 'ar' ? 'لكزس' : 'Lexus'}</option>
                    <option value="جي ام سي">{lang === 'ar' ? 'جي ام سي' : 'GMC'}</option>
                    <option value="لاند روفر">{lang === 'ar' ? 'لاند روفر' : 'Land Rover'}</option>
                    <option value="بورشه">{lang === 'ar' ? 'بورشه' : 'Porsche'}</option>
                    <option value="أخرى">{lang === 'ar' ? 'أخرى' : 'Other'}</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('category')}
                  </label>
                  <select name="category" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">-- {t('category')} --</option>
                    <option value="سيدان">{lang === 'ar' ? 'سيدان' : 'Sedan'}</option>
                    <option value="SUV">SUV</option>
                    <option value="كوبيه">{lang === 'ar' ? 'كوبيه' : 'Coupe'}</option>
                    <option value="بيك أب">{lang === 'ar' ? 'بيك أب' : 'Pickup'}</option>
                    <option value="فان">{lang === 'ar' ? 'فان' : 'Van'}</option>
                    <option value="رياضية">{lang === 'ar' ? 'رياضية' : 'Sport'}</option>
                    <option value="كلاسيك">{lang === 'ar' ? 'كلاسيك' : 'Classic'}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('seats')}
                  </label>
                  <select name="seats" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">{lang === 'ar' ? '-- المقاعد --' : '-- Seats --'}</option>
                    <option value="2">2</option>
                    <option value="4">4</option>
                    <option value="5">5</option>
                    <option value="7">7</option>
                    <option value="8">8</option>
                    <option value="9">9</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('transmission')}
                  </label>
                  <select name="transmission" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="AUTOMATIC">{t('automatic')}</option>
                    <option value="MANUAL">{t('manual')}</option>
                    <option value="ELECTRIC">{t('electric')}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('minAge')}
                  </label>
                  <select name="minAge" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">{lang === 'ar' ? '-- العمر --' : '-- Age --'}</option>
                    <option value="18">18</option>
                    <option value="21">21</option>
                    <option value="25">25</option>
                    <option value="30">30</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('smokingPolicy')}
                  </label>
                  <select name="smokingPolicy" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="ممنوع">{lang === 'ar' ? 'ممنوع' : 'No Smoking'}</option>
                    <option value="مسموح">{lang === 'ar' ? 'مسموح' : 'Allowed'}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-text-primary">
                    {t('distancePolicy')}
                  </label>
                  <select name="distancePolicy" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                    <option value="">{lang === 'ar' ? '-- المسافة --' : '-- Distance --'}</option>
                    <option value="مفتوحة">{lang === 'ar' ? 'مفتوحة (بدون حد)' : 'Unlimited'}</option>
                    <option value="100 كم/يوم">{lang === 'ar' ? '100 كم/يوم' : '100 km/day'}</option>
                    <option value="150 كم/يوم">{lang === 'ar' ? '150 كم/يوم' : '150 km/day'}</option>
                    <option value="200 كم/يوم">{lang === 'ar' ? '200 كم/يوم' : '200 km/day'}</option>
                    <option value="250 كم/يوم">{lang === 'ar' ? '250 كم/يوم' : '250 km/day'}</option>
                    <option value="300 كم/يوم">{lang === 'ar' ? '300 كم/يوم' : '300 km/day'}</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {t('availability')}
                </label>
                <select name="availabilityText" className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50">
                  <option value="">{lang === 'ar' ? '-- التوفر --' : '-- Availability --'}</option>
                  <option value="متاح يومياً">{lang === 'ar' ? 'متاح يومياً' : 'Available daily'}</option>
                  <option value="أيام العمل فقط">{lang === 'ar' ? 'أيام العمل فقط' : 'Weekdays only'}</option>
                  <option value="عطلة نهاية الأسبوع">{lang === 'ar' ? 'عطلة نهاية الأسبوع فقط' : 'Weekends only'}</option>
                  <option value="حسب الاتفاق">{lang === 'ar' ? 'حسب الاتفاق' : 'By arrangement'}</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {t('notes')}
                </label>
                <textarea
                  name="notes"
                  rows={3}
                  placeholder={t('notes')}
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-dark-border-light focus:ring-2 focus:ring-dark-border/50"
                />
              </div>
            </div>
          </div>

          {/* Images */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'الصور والمستندات' : 'Images & Documents'}
            </h2>

            <div className="space-y-6">
              {/* Car Images */}
              <div>
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-text-primary">
                  <ImageIcon className="h-4 w-4 text-status-star" />
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

                  <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                    {uploading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
                    ) : (
                      <>
                        <Upload className="mb-1 h-5 w-5 text-text-muted" />
                        <span className="text-[10px] text-text-muted">
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
                <label className="mb-2 flex items-center gap-2 text-sm font-medium text-text-primary">
                  <FileText className="h-4 w-4 text-status-star" />
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

                  <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                    {uploading ? (
                      <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
                    ) : (
                      <>
                        <Upload className="mb-1 h-5 w-5 text-text-muted" />
                        <span className="text-[10px] text-text-muted">
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
            <div className="flex items-center gap-2 rounded-xl bg-status-warning/10 p-4 text-sm text-status-warning border border-status-warning/20">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={pending || uploading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-4 text-lg font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
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
