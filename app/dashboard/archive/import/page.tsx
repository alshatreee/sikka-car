'use client'

import { useState } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import { Upload, ArrowRight, Loader2, CheckCircle, AlertTriangle } from 'lucide-react'

const ITEM_TYPES = [
  { value: 'BOOK', labelAr: 'كتاب', labelEn: 'Book' },
  { value: 'MANUSCRIPT', labelAr: 'مخطوطة', labelEn: 'Manuscript' },
  { value: 'DOCUMENT', labelAr: 'وثيقة', labelEn: 'Document' },
  { value: 'ARTICLE', labelAr: 'مقال', labelEn: 'Article' },
  { value: 'IMAGE', labelAr: 'صورة', labelEn: 'Image' },
  { value: 'AUDIO', labelAr: 'ملف صوتي', labelEn: 'Audio' },
  { value: 'VIDEO', labelAr: 'ملف مرئي', labelEn: 'Video' },
  { value: 'PUBLICATION', labelAr: 'إصدار', labelEn: 'Publication' },
]

function generateSlug(title: string): string {
  return title
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\u0600-\u06FFa-zA-Z0-9-]/g, '')
    .slice(0, 80)
    .concat('-', Date.now().toString(36))
}

export default function ImportPage() {
  const { lang } = useLanguage()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ success: boolean; error?: string; slug?: string } | null>(null)

  const [form, setForm] = useState({
    titleAr: '',
    titleEn: '',
    descriptionAr: '',
    itemType: 'BOOK',
    creator: '',
    contributor: '',
    publisher: '',
    publicationYear: '',
    coveragePlace: '',
    coveragePeriod: '',
    collectionName: '',
    kuwaitPeriod: '',
    verificationStatus: '',
    tags: '',
  })

  function updateField(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.titleAr.trim()) return

    setLoading(true)
    setResult(null)

    try {
      const res = await fetch('/api/archive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          slug: generateSlug(form.titleAr),
          publicationYear: form.publicationYear ? parseInt(form.publicationYear) : undefined,
          tags: form.tags ? form.tags.split('،').map((t) => t.trim()).filter(Boolean) : [],
          status: 'DRAFT',
        }),
      })

      const data = await res.json()
      if (res.ok && data.success) {
        setResult({ success: true, slug: data.slug })
        setForm({
          titleAr: '', titleEn: '', descriptionAr: '', itemType: 'BOOK',
          creator: '', contributor: '', publisher: '', publicationYear: '',
          coveragePlace: '', coveragePeriod: '', collectionName: '',
          kuwaitPeriod: '', verificationStatus: '', tags: '',
        })
      } else {
        setResult({ success: false, error: data.error || 'فشل الإنشاء' })
      }
    } catch {
      setResult({ success: false, error: 'فشل الاتصال بالخادم' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-status-star/10 border border-status-star/20">
              <Upload className="h-5 w-5 text-status-star" />
            </div>
            <h1 className="text-lg font-bold text-text-primary">
              {lang === 'ar' ? 'إضافة عنصر للأرشيف' : 'Add Archive Item'}
            </h1>
          </div>
          <Link
            href="/dashboard/archive/items"
            className="flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'قائمة العناصر' : 'Items List'}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {/* Result */}
        {result && (
          <div className={`mb-4 rounded-xl border p-4 text-sm ${result.success ? 'border-green-500/20 bg-green-500/5 text-green-400' : 'border-red-500/20 bg-red-500/5 text-red-400'}`}>
            <div className="flex items-center gap-2">
              {result.success ? <CheckCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
              {result.success ? (
                <span>
                  {lang === 'ar' ? 'تم الإنشاء بنجاح.' : 'Created successfully.'}{' '}
                  <Link href={`/archive/item/${result.slug}`} className="underline">
                    {lang === 'ar' ? 'عرض العنصر' : 'View item'}
                  </Link>
                </span>
              ) : (
                <span>{result.error}</span>
              )}
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-dark-border bg-dark-card p-6" dir="rtl">
          {/* Title */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">العنوان بالعربية *</label>
              <input
                value={form.titleAr}
                onChange={(e) => updateField('titleAr', e.target.value)}
                className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">العنوان بالإنجليزية</label>
              <input
                value={form.titleEn}
                onChange={(e) => updateField('titleEn', e.target.value)}
                className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light"
                dir="ltr"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="mb-1 block text-xs font-medium text-text-secondary">الوصف</label>
            <textarea
              value={form.descriptionAr}
              onChange={(e) => updateField('descriptionAr', e.target.value)}
              rows={4}
              className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light"
            />
          </div>

          {/* Type */}
          <div>
            <label className="mb-1 block text-xs font-medium text-text-secondary">نوع العنصر *</label>
            <div className="flex flex-wrap gap-2">
              {ITEM_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => updateField('itemType', t.value)}
                  className={`rounded-lg border px-3 py-1.5 text-xs transition-all ${form.itemType === t.value ? 'border-status-star bg-status-star/10 text-status-star' : 'border-dark-border text-text-secondary hover:border-dark-border-light'}`}
                >
                  {lang === 'ar' ? t.labelAr : t.labelEn}
                </button>
              ))}
            </div>
          </div>

          {/* Creator / Contributor / Publisher */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">المؤلف</label>
              <input value={form.creator} onChange={(e) => updateField('creator', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">المحقق</label>
              <input value={form.contributor} onChange={(e) => updateField('contributor', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">الناشر</label>
              <input value={form.publisher} onChange={(e) => updateField('publisher', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
          </div>

          {/* Year / Place / Period */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">سنة النشر</label>
              <input value={form.publicationYear} onChange={(e) => updateField('publicationYear', e.target.value)} type="number" className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" dir="ltr" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">المنطقة</label>
              <input value={form.coveragePlace} onChange={(e) => updateField('coveragePlace', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">الفترة الزمنية</label>
              <input value={form.coveragePeriod} onChange={(e) => updateField('coveragePeriod', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
          </div>

          {/* Collection / Kuwait Period / Verification */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">المجموعة</label>
              <input value={form.collectionName} onChange={(e) => updateField('collectionName', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">الفترة الكويتية</label>
              <input value={form.kuwaitPeriod} onChange={(e) => updateField('kuwaitPeriod', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">حالة التحقيق</label>
              <select value={form.verificationStatus} onChange={(e) => updateField('verificationStatus', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light">
                <option value="">— اختر —</option>
                <option value="محقق">محقق</option>
                <option value="غير محقق">غير محقق</option>
                <option value="قيد التحقيق">قيد التحقيق</option>
              </select>
            </div>
          </div>

          {/* Tags */}
          <div>
            <label className="mb-1 block text-xs font-medium text-text-secondary">الوسوم (افصل بفاصلة عربية ،)</label>
            <input value={form.tags} onChange={(e) => updateField('tags', e.target.value)} className="w-full rounded-xl border border-dark-border bg-dark-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-dark-border-light" placeholder="تاريخ، كويت، مخطوطة" />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!form.titleAr.trim() || loading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3.5 font-medium text-text-primary shadow-lg transition-all hover:bg-brand-solid-hover disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                جارٍ الإنشاء...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                إنشاء العنصر
              </>
            )}
          </button>
        </form>
      </div>
    </main>
  )
}
