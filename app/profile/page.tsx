'use client'

import { useEffect, useState, useTransition } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import { getProfile, updateProfile } from '@/actions/profileActions'
import { User, CreditCard, Car, Save, Loader2, CheckCircle } from 'lucide-react'

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
  const [drivingLicense, setDrivingLicense] = useState('')

  useEffect(() => {
    getProfile().then((data) => {
      if (data) {
        setFullName(data.fullName || '')
        setEmail(data.email || '')
        setPhone(data.phone || '')
        setCivilId(data.civilId || '')
        setDrivingLicense(data.drivingLicense || '')
      }
      setLoading(false)
    })
  }, [])

  function handleSave() {
    setError('')
    setSaved(false)
    startTransition(async () => {
      const result = await updateProfile({ fullName, phone, civilId, drivingLicense })
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

          {/* ID & License */}
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
              <CreditCard className="h-5 w-5 text-status-star" />
              {lang === 'ar' ? 'الهوية والرخصة' : 'ID & License'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-text-primary">
                  {lang === 'ar' ? 'الرقم المدني' : 'Civil ID'}
                </label>
                <input
                  value={civilId}
                  onChange={(e) => setCivilId(e.target.value)}
                  dir="ltr"
                  className="w-full rounded-xl border border-dark-border bg-dark-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-dark-border-light"
                  placeholder={lang === 'ar' ? 'أدخل الرقم المدني' : 'Enter civil ID'}
                />
              </div>
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
