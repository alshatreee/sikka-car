'use client'

import { useEffect, useState, useTransition } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { getProfile, updateProfile } from '@/actions/profileActions'
import { uploadToCloudinary } from '@/utils/uploadImage'
import { User, CreditCard, Save, Loader2, CheckCircle, Camera, Check, Shield } from 'lucide-react'
import Image from 'next/image'

export default function ProfilePage() {
  const { lang } = useLanguage()
  const [pending, startTransition] = useTransition()
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [civilId, setCivilId] = useState('')
  const [civilIdImageFront, setCivilIdImageFront] = useState('')
  const [civilIdImageBack, setCivilIdImageBack] = useState('')
  const [drivingLicense, setDrivingLicense] = useState('')
  const [drivingLicenseImageFront, setDrivingLicenseImageFront] = useState('')
  const [drivingLicenseImageBack, setDrivingLicenseImageBack] = useState('')
  const [uploadingCivilFront, setUploadingCivilFront] = useState(false)
  const [uploadingCivilBack, setUploadingCivilBack] = useState(false)
  const [uploadingLicenseFront, setUploadingLicenseFront] = useState(false)
  const [uploadingLicenseBack, setUploadingLicenseBack] = useState(false)

  useEffect(() => {
    getProfile().then((data) => {
      if (data) {
        setFullName(data.fullName || '')
        setEmail(data.email || '')
        setPhone(data.phone || '')
        setCivilId(data.civilId || '')
        setCivilIdImageFront(data.civilIdImageFront || '')
        setCivilIdImageBack(data.civilIdImageBack || '')
        setDrivingLicense(data.drivingLicense || '')
        setDrivingLicenseImageFront(data.drivingLicenseImageFront || '')
        setDrivingLicenseImageBack(data.drivingLicenseImageBack || '')
      }
      setLoading(false)
    })
  }, [])

  function handleSave() {
    setError('')
    setSaved(false)
    startTransition(async () => {
      const result = await updateProfile({
        fullName,
        phone,
        civilId,
        civilIdImageFront,
        civilIdImageBack,
        drivingLicense,
        drivingLicenseImageFront,
        drivingLicenseImageBack,
      })
      if (result.success) {
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
      } else {
        setError(result.error || '')
      }
    })
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
      <div className="mx-auto max-w-xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-card border border-dark-border">
            <User className="h-8 w-8 text-status-star" />
          </div>
          <h1 className="mb-2 text-3xl font-bold text-text-primary">
            {lang === 'ar' ? 'الملف الشخصي' : 'My Profile'}
          </h1>
          <p className="text-text-secondary">
            {lang === 'ar' ? 'أكمل بياناتك لتتمكن من الحجز' : 'Complete your info to book cars'}
          </p>
        </div>

        <div className="space-y-6">
          {/* Basic Info */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
              <User className="h-5 w-5 text-status-star" />
              {lang === 'ar' ? 'البيانات الأساسية' : 'Basic Info'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'الاسم الكامل' : 'Full Name'}
                </label>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-dark-border-light"
                  placeholder={lang === 'ar' ? 'الاسم الكامل' : 'Full name'}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'البريد الإلكتروني' : 'Email'}
                </label>
                <input
                  value={email}
                  disabled
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-muted outline-none opacity-60"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'رقم الهاتف' : 'Phone'}
                </label>
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  dir="ltr"
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-dark-border-light"
                  placeholder="+965 XXXX XXXX"
                />
              </div>
            </div>
          </div>

          {/* Civil ID */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
              <Shield className="h-5 w-5 text-status-star" />
              {lang === 'ar' ? 'البطاقة المدنية' : 'Civil ID'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'الرقم المدني' : 'Civil ID Number'}
                </label>
                <input
                  value={civilId}
                  onChange={(e) => setCivilId(e.target.value)}
                  dir="ltr"
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-dark-border-light"
                  placeholder={lang === 'ar' ? 'أدخل الرقم المدني' : 'Enter civil ID'}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-2 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'الوجه الأمامي' : 'Front Side'}
                  </label>
                  {civilIdImageFront ? (
                    <div className="relative h-32 w-full overflow-hidden rounded-xl border border-green-500/30">
                      <Image src={civilIdImageFront} alt="Civil ID Front" fill className="object-cover" />
                      <div className="absolute top-2 end-2 flex gap-2">
                        <span className="flex items-center gap-1 rounded-lg bg-green-500/20 px-2 py-1 text-xs text-green-400 border border-green-500/30">
                          <Check className="h-3 w-3" />
                        </span>
                        <button type="button" onClick={() => setCivilIdImageFront('')} className="rounded-lg bg-dark-bg/80 px-2 py-1 text-xs text-text-muted hover:text-text-primary">
                          {lang === 'ar' ? 'حذف' : 'Remove'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                      {uploadingCivilFront ? (
                        <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
                      ) : (
                        <>
                          <Camera className="mb-2 h-8 w-8 text-text-muted" />
                          <span className="text-sm text-text-muted">
                            {lang === 'ar' ? 'الوجه الأمامي' : 'Front Side'}
                          </span>
                        </>
                      )}
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file) return
                        setUploadingCivilFront(true)
                        const url = await uploadToCloudinary(file, 'sikka_id_docs')
                        if (url) setCivilIdImageFront(url)
                        setUploadingCivilFront(false)
                      }} />
                    </label>
                  )}
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'الوجه الخلفي' : 'Back Side'}
                  </label>
                  {civilIdImageBack ? (
                    <div className="relative h-32 w-full overflow-hidden rounded-xl border border-green-500/30">
                      <Image src={civilIdImageBack} alt="Civil ID Back" fill className="object-cover" />
                      <div className="absolute top-2 end-2 flex gap-2">
                        <span className="flex items-center gap-1 rounded-lg bg-green-500/20 px-2 py-1 text-xs text-green-400 border border-green-500/30">
                          <Check className="h-3 w-3" />
                        </span>
                        <button type="button" onClick={() => setCivilIdImageBack('')} className="rounded-lg bg-dark-bg/80 px-2 py-1 text-xs text-text-muted hover:text-text-primary">
                          {lang === 'ar' ? 'حذف' : 'Remove'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                      {uploadingCivilBack ? (
                        <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
                      ) : (
                        <>
                          <Camera className="mb-2 h-8 w-8 text-text-muted" />
                          <span className="text-sm text-text-muted">
                            {lang === 'ar' ? 'الوجه الخلفي' : 'Back Side'}
                          </span>
                        </>
                      )}
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file) return
                        setUploadingCivilBack(true)
                        const url = await uploadToCloudinary(file, 'sikka_id_docs')
                        if (url) setCivilIdImageBack(url)
                        setUploadingCivilBack(false)
                      }} />
                    </label>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Driving License */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
              <CreditCard className="h-5 w-5 text-status-star" />
              {lang === 'ar' ? 'رخصة القيادة' : 'Driving License'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'رقم رخصة القيادة' : 'Driving License Number'}
                </label>
                <input
                  value={drivingLicense}
                  onChange={(e) => setDrivingLicense(e.target.value)}
                  dir="ltr"
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-dark-border-light"
                  placeholder={lang === 'ar' ? 'أدخل رقم الرخصة' : 'Enter license number'}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-2 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'الوجه الأمامي' : 'Front Side'}
                  </label>
                  {drivingLicenseImageFront ? (
                    <div className="relative h-32 w-full overflow-hidden rounded-xl border border-green-500/30">
                      <Image src={drivingLicenseImageFront} alt="License Front" fill className="object-cover" />
                      <div className="absolute top-2 end-2 flex gap-2">
                        <span className="flex items-center gap-1 rounded-lg bg-green-500/20 px-2 py-1 text-xs text-green-400 border border-green-500/30">
                          <Check className="h-3 w-3" />
                        </span>
                        <button type="button" onClick={() => setDrivingLicenseImageFront('')} className="rounded-lg bg-dark-bg/80 px-2 py-1 text-xs text-text-muted hover:text-text-primary">
                          {lang === 'ar' ? 'حذف' : 'Remove'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                      {uploadingLicenseFront ? (
                        <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
                      ) : (
                        <>
                          <Camera className="mb-2 h-8 w-8 text-text-muted" />
                          <span className="text-sm text-text-muted">
                            {lang === 'ar' ? 'الوجه الأمامي' : 'Front Side'}
                          </span>
                        </>
                      )}
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file) return
                        setUploadingLicenseFront(true)
                        const url = await uploadToCloudinary(file, 'sikka_id_docs')
                        if (url) setDrivingLicenseImageFront(url)
                        setUploadingLicenseFront(false)
                      }} />
                    </label>
                  )}
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-text-primary">
                    {lang === 'ar' ? 'الوجه الخلفي' : 'Back Side'}
                  </label>
                  {drivingLicenseImageBack ? (
                    <div className="relative h-32 w-full overflow-hidden rounded-xl border border-green-500/30">
                      <Image src={drivingLicenseImageBack} alt="License Back" fill className="object-cover" />
                      <div className="absolute top-2 end-2 flex gap-2">
                        <span className="flex items-center gap-1 rounded-lg bg-green-500/20 px-2 py-1 text-xs text-green-400 border border-green-500/30">
                          <Check className="h-3 w-3" />
                        </span>
                        <button type="button" onClick={() => setDrivingLicenseImageBack('')} className="rounded-lg bg-dark-bg/80 px-2 py-1 text-xs text-text-muted hover:text-text-primary">
                          {lang === 'ar' ? 'حذف' : 'Remove'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-dark-border transition-colors hover:border-status-star/50 hover:bg-dark-surface">
                      {uploadingLicenseBack ? (
                        <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
                      ) : (
                        <>
                          <Camera className="mb-2 h-8 w-8 text-text-muted" />
                          <span className="text-sm text-text-muted">
                            {lang === 'ar' ? 'الوجه الخلفي' : 'Back Side'}
                          </span>
                        </>
                      )}
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file) return
                        setUploadingLicenseBack(true)
                        const url = await uploadToCloudinary(file, 'sikka_id_docs')
                        if (url) setDrivingLicenseImageBack(url)
                        setUploadingLicenseBack(false)
                      }} />
                    </label>
                  )}
                </div>
              </div>
            </div>
          </div>

          {saved && (
            <div className="flex items-center gap-2 rounded-xl bg-green-500/10 p-3 text-sm text-green-400 border border-green-500/20">
              <CheckCircle className="h-4 w-4" />
              {lang === 'ar' ? 'تم حفظ البيانات بنجاح' : 'Profile saved successfully'}
            </div>
          )}

          {error && (
            <div className="rounded-xl bg-status-warning/10 p-3 text-sm text-status-warning border border-status-warning/20">
              {error}
            </div>
          )}

          <button
            onClick={handleSave}
            disabled={pending}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:opacity-50"
          >
            {pending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Save className="h-5 w-5" />
            )}
            {pending
              ? (lang === 'ar' ? 'جاري الحفظ...' : 'Saving...')
              : (lang === 'ar' ? 'حفظ البيانات' : 'Save Profile')}
          </button>
        </div>
      </div>
    </main>
  )
}
