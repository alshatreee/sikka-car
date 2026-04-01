'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useLanguage } from '@/components/shared/LanguageProvider'
import {
  BookOpen,
  Download,
  ArrowRight,
  FileText,
  Sparkles,
  Users,
  MapPin,
  Calendar,
  Tag,
  Loader2,
} from 'lucide-react'

interface ArchiveItemDetail {
  id: string
  slug: string
  titleAr: string
  titleEn: string | null
  descriptionAr: string | null
  descriptionEn: string | null
  itemType: string
  status: string
  language: string | null
  creator: string | null
  contributor: string | null
  publisher: string | null
  identifier: string | null
  sourceReference: string | null
  rightsStatement: string | null
  publicationYear: number | null
  coveragePlace: string | null
  coveragePeriod: string | null
  collectionName: string | null
  kuwaitPeriod: string | null
  manuscriptNotes: string | null
  verificationStatus: string | null
  coverImageUrl: string | null
  hasOcr: boolean
  searchText: string | null
  tags: string[]
  createdAt: string
  files: ArchiveFile[]
  itemPeople: {
    role: string | null
    person: { nameAr: string; nameEn: string | null; slug: string }
  }[]
  itemSubjects: {
    subject: { nameAr: string; nameEn: string | null; slug: string }
  }[]
}

interface ArchiveFile {
  id: string
  fileKind: string
  publicUrl: string | null
  mimeType: string | null
  fileSize: number | null
  pageCount: number | null
  isPrimary: boolean
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ArchiveItemPage() {
  const params = useParams()
  const slug = params?.slug as string
  const { lang } = useLanguage()

  const [item, setItem] = useState<ArchiveItemDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analyzingFull, setAnalyzingFull] = useState(false)
  const [analyzingEntities, setAnalyzingEntities] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<string | null>(null)
  const [entitiesResult, setEntitiesResult] = useState<string | null>(null)

  const isAr = lang === 'ar'

  useEffect(() => {
    if (!slug) return

    async function fetchItem() {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/archive/item/${slug}`)
        if (!res.ok) {
          throw new Error(isAr ? 'تعذر تحميل العنصر' : 'Failed to load item')
        }
        const data = await res.json()
        setItem(data)
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : isAr
              ? 'حدث خطأ غير متوقع'
              : 'An unexpected error occurred'
        )
      } finally {
        setLoading(false)
      }
    }

    fetchItem()
  }, [slug, isAr])

  const handleAnalyzeFull = useCallback(async () => {
    if (!item?.searchText) return
    setAnalyzingFull(true)
    setAnalysisResult(null)
    try {
      const res = await fetch('/api/kazima-ai/analyze-full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: item.searchText }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setAnalysisResult(data.result ?? JSON.stringify(data, null, 2))
    } catch {
      setAnalysisResult(
        isAr ? 'فشل التحليل. حاول مرة أخرى.' : 'Analysis failed. Please try again.'
      )
    } finally {
      setAnalyzingFull(false)
    }
  }, [item?.searchText, isAr])

  const handleExtractEntities = useCallback(async () => {
    if (!item?.searchText) return
    setAnalyzingEntities(true)
    setEntitiesResult(null)
    try {
      const res = await fetch('/api/kazima-ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: item.searchText, mode: 'extraction' }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setEntitiesResult(data.result ?? JSON.stringify(data, null, 2))
    } catch {
      setEntitiesResult(
        isAr ? 'فشل الاستخراج. حاول مرة أخرى.' : 'Extraction failed. Please try again.'
      )
    } finally {
      setAnalyzingEntities(false)
    }
  }, [item?.searchText, isAr])

  const title = item
    ? isAr
      ? item.titleAr
      : item.titleEn ?? item.titleAr
    : ''

  const description = item
    ? isAr
      ? item.descriptionAr
      : item.descriptionEn ?? item.descriptionAr
    : null

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-status-star" />
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <BookOpen className="mx-auto mb-4 h-12 w-12 text-text-muted" />
        <h1 className="mb-2 text-xl font-bold text-text-primary">
          {isAr ? 'لم يتم العثور على العنصر' : 'Item not found'}
        </h1>
        <p className="mb-6 text-text-secondary">
          {error ?? (isAr ? 'العنصر غير موجود أو تم حذفه.' : 'The item does not exist or has been removed.')}
        </p>
        <Link
          href="/archive"
          className="inline-flex items-center gap-2 rounded-xl bg-dark-card px-5 py-2.5 text-sm font-medium text-status-star transition-colors hover:bg-dark-surface"
        >
          <ArrowRight className="h-4 w-4" />
          {isAr ? 'العودة للأرشيف' : 'Back to Archive'}
        </Link>
      </div>
    )
  }

  const dublinCoreFields: { labelAr: string; labelEn: string; value: string | null | undefined; icon: React.ReactNode }[] = [
    { labelAr: 'المنشئ', labelEn: 'Creator', value: item.creator, icon: <Users className="h-4 w-4" /> },
    { labelAr: 'المساهم', labelEn: 'Contributor', value: item.contributor, icon: <Users className="h-4 w-4" /> },
    { labelAr: 'الناشر', labelEn: 'Publisher', value: item.publisher, icon: <BookOpen className="h-4 w-4" /> },
    { labelAr: 'سنة النشر', labelEn: 'Publication Year', value: item.publicationYear?.toString(), icon: <Calendar className="h-4 w-4" /> },
    { labelAr: 'اللغة', labelEn: 'Language', value: item.language, icon: <FileText className="h-4 w-4" /> },
    { labelAr: 'المعرّف', labelEn: 'Identifier', value: item.identifier, icon: <Tag className="h-4 w-4" /> },
    { labelAr: 'المرجع', labelEn: 'Source Reference', value: item.sourceReference, icon: <FileText className="h-4 w-4" /> },
    { labelAr: 'الحقوق', labelEn: 'Rights', value: item.rightsStatement, icon: <FileText className="h-4 w-4" /> },
    { labelAr: 'المكان', labelEn: 'Coverage (Place)', value: item.coveragePlace, icon: <MapPin className="h-4 w-4" /> },
    { labelAr: 'الفترة الزمنية', labelEn: 'Coverage (Period)', value: item.coveragePeriod, icon: <Calendar className="h-4 w-4" /> },
    { labelAr: 'المجموعة', labelEn: 'Collection', value: item.collectionName, icon: <BookOpen className="h-4 w-4" /> },
    { labelAr: 'الحقبة الكويتية', labelEn: 'Kuwait Period', value: item.kuwaitPeriod, icon: <Calendar className="h-4 w-4" /> },
    { labelAr: 'ملاحظات المخطوطة', labelEn: 'Manuscript Notes', value: item.manuscriptNotes, icon: <FileText className="h-4 w-4" /> },
  ]

  const visibleDublinCore = dublinCoreFields.filter((f) => f.value)

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Back link */}
      <Link
        href="/archive"
        className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-text-secondary transition-colors hover:text-status-star"
      >
        <ArrowRight className="h-4 w-4" />
        {isAr ? 'العودة للأرشيف' : 'Back to Archive'}
      </Link>

      {/* Header */}
      <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-dark-surface px-3 py-1 text-xs font-medium text-status-star">
            <BookOpen className="h-3.5 w-3.5" />
            {item.itemType}
          </span>
          <span className="inline-flex items-center rounded-full bg-dark-surface px-3 py-1 text-xs font-medium text-text-muted">
            {item.status}
          </span>
          {item.hasOcr && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-status-star/10 px-3 py-1 text-xs font-medium text-status-star">
              <FileText className="h-3.5 w-3.5" />
              OCR
            </span>
          )}
          {item.verificationStatus && (
            <span className="inline-flex items-center rounded-full bg-dark-surface px-3 py-1 text-xs font-medium text-text-muted">
              {item.verificationStatus}
            </span>
          )}
        </div>

        <h1 className="mb-3 text-2xl font-bold leading-tight text-text-primary">
          {title}
        </h1>

        {description && (
          <p className="whitespace-pre-line text-sm leading-relaxed text-text-secondary">
            {description}
          </p>
        )}
      </div>

      {/* Dublin Core Metadata */}
      {visibleDublinCore.length > 0 && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-4 text-lg font-bold text-text-primary">
            {isAr ? 'بيانات دبلن كور' : 'Dublin Core Metadata'}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {visibleDublinCore.map((field, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0 text-text-muted">
                  {field.icon}
                </div>
                <div className="min-w-0">
                  <dt className="text-xs font-medium text-text-muted">
                    {isAr ? field.labelAr : field.labelEn}
                  </dt>
                  <dd className="mt-0.5 text-sm text-text-primary">
                    {field.value}
                  </dd>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* People */}
      {item.itemPeople.length > 0 && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
            <Users className="h-5 w-5 text-status-star" />
            {isAr ? 'الأشخاص' : 'People'}
          </h2>
          <ul className="space-y-3">
            {item.itemPeople.map((ip, i) => (
              <li key={i} className="flex items-center justify-between rounded-xl bg-dark-surface px-4 py-3">
                <Link
                  href={`/archive/person/${ip.person.slug}`}
                  className="text-sm font-medium text-text-primary transition-colors hover:text-status-star"
                >
                  {isAr ? ip.person.nameAr : ip.person.nameEn ?? ip.person.nameAr}
                </Link>
                {ip.role && (
                  <span className="text-xs text-text-muted">{ip.role}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Subjects */}
      {item.itemSubjects.length > 0 && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
            <Tag className="h-5 w-5 text-status-star" />
            {isAr ? 'المواضيع' : 'Subjects'}
          </h2>
          <div className="flex flex-wrap gap-2">
            {item.itemSubjects.map((is_, i) => (
              <Link
                key={i}
                href={`/archive/subject/${is_.subject.slug}`}
                className="inline-flex items-center rounded-full bg-dark-surface px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:text-status-star"
              >
                {isAr ? is_.subject.nameAr : is_.subject.nameEn ?? is_.subject.nameAr}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Tags */}
      {item.tags.length > 0 && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
            <Tag className="h-5 w-5 text-status-star" />
            {isAr ? 'الوسوم' : 'Tags'}
          </h2>
          <div className="flex flex-wrap gap-2">
            {item.tags.map((tag, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-full bg-status-star/10 px-3 py-1.5 text-xs font-medium text-status-star"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Files */}
      {item.files.length > 0 && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
            <FileText className="h-5 w-5 text-status-star" />
            {isAr ? 'الملفات المرفقة' : 'Attached Files'}
          </h2>
          <ul className="space-y-3">
            {item.files.map((file) => (
              <li
                key={file.id}
                className="flex items-center justify-between rounded-xl bg-dark-surface px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">
                      {file.fileKind}
                    </span>
                    {file.isPrimary && (
                      <span className="rounded bg-status-star/10 px-1.5 py-0.5 text-[10px] font-bold uppercase text-status-star">
                        {isAr ? 'أساسي' : 'Primary'}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-text-muted">
                    {file.mimeType && <span>{file.mimeType}</span>}
                    {file.fileSize && <span>{formatFileSize(file.fileSize)}</span>}
                    {file.pageCount && (
                      <span>
                        {file.pageCount} {isAr ? 'صفحة' : 'pages'}
                      </span>
                    )}
                  </div>
                </div>
                {file.publicUrl && (
                  <a
                    href={file.publicUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    download
                    className="flex-shrink-0 rounded-lg bg-dark-card p-2 text-text-secondary transition-colors hover:text-status-star"
                    title={isAr ? 'تحميل' : 'Download'}
                  >
                    <Download className="h-4 w-4" />
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* OCR Status */}
      {item.hasOcr && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-2 flex items-center gap-2 text-lg font-bold text-text-primary">
            <FileText className="h-5 w-5 text-status-star" />
            {isAr ? 'حالة التعرف الضوئي' : 'OCR Status'}
          </h2>
          <p className="text-sm text-text-secondary">
            {isAr
              ? 'تم استخراج النص من هذا العنصر باستخدام التعرف الضوئي على الحروف (OCR).'
              : 'Text has been extracted from this item using Optical Character Recognition (OCR).'}
          </p>
          {item.searchText && (
            <details className="mt-4">
              <summary className="cursor-pointer text-sm font-medium text-status-star hover:underline">
                {isAr ? 'عرض النص المستخرج' : 'View extracted text'}
              </summary>
              <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-dark-surface p-4 text-xs leading-relaxed text-text-secondary">
                {item.searchText}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* Kazima AI Actions */}
      {item.searchText && (
        <div className="mb-8 rounded-2xl border border-dark-border bg-dark-card p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-text-primary">
            <Sparkles className="h-5 w-5 text-status-star" />
            {isAr ? 'تحليل بالذكاء الاصطناعي' : 'AI Analysis'}
          </h2>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleAnalyzeFull}
              disabled={analyzingFull}
              className="inline-flex items-center gap-2 rounded-xl bg-status-star px-5 py-2.5 text-sm font-bold text-dark-card transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {analyzingFull ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {isAr ? 'حلل هذا العنصر' : 'Analyze with Kazima AI'}
            </button>
            <button
              onClick={handleExtractEntities}
              disabled={analyzingEntities}
              className="inline-flex items-center gap-2 rounded-xl border border-status-star bg-transparent px-5 py-2.5 text-sm font-bold text-status-star transition-colors hover:bg-status-star/10 disabled:opacity-50"
            >
              {analyzingEntities ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Tag className="h-4 w-4" />
              )}
              {isAr ? 'استخرج الكيانات' : 'Extract Entities'}
            </button>
          </div>

          {analysisResult && (
            <div className="mt-4 rounded-xl bg-dark-surface p-4">
              <h3 className="mb-2 text-sm font-bold text-text-primary">
                {isAr ? 'نتيجة التحليل' : 'Analysis Result'}
              </h3>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">
                {analysisResult}
              </pre>
            </div>
          )}

          {entitiesResult && (
            <div className="mt-4 rounded-xl bg-dark-surface p-4">
              <h3 className="mb-2 text-sm font-bold text-text-primary">
                {isAr ? 'الكيانات المستخرجة' : 'Extracted Entities'}
              </h3>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">
                {entitiesResult}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
