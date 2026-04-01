'use client'

import { useState, useEffect } from 'react'
import { useLanguage } from '@/components/shared/LanguageProvider'
import Link from 'next/link'
import { Users, ArrowRight, Loader2 } from 'lucide-react'
import { getArchivePeople } from '@/actions/archiveActions'

interface Person {
  id: string
  nameAr: string
  nameEn: string | null
  bio: string | null
  birthYear: number | null
  deathYear: number | null
  slug: string
}

export default function PeoplePage() {
  const { lang } = useLanguage()
  const [people, setPeople] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getArchivePeople()
      .then((data) => setPeople(data.people as Person[]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="container py-8 pb-24 md:pb-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/20">
              <Users className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text-primary">
                {lang === 'ar' ? 'الأعلام والمؤلفون' : 'Scholars & Authors'}
              </h1>
              <p className="text-xs text-text-muted">
                {lang === 'ar' ? 'الأشخاص المرتبطون بالأرشيف' : 'People linked to archive items'}
              </p>
            </div>
          </div>
          <Link
            href="/archive"
            className="flex items-center gap-1 rounded-lg border border-dark-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-dark-surface"
          >
            {lang === 'ar' ? 'الأرشيف' : 'Archive'}
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
          </div>
        ) : people.length === 0 ? (
          <div className="rounded-2xl border border-dark-border bg-dark-card p-12 text-center">
            <Users className="mx-auto mb-3 h-10 w-10 text-text-muted" />
            <p className="text-sm text-text-secondary">
              {lang === 'ar' ? 'لا يوجد أشخاص مسجلون بعد' : 'No people registered yet'}
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {people.map((person) => (
              <div
                key={person.id}
                className="group rounded-xl border border-dark-border bg-dark-card p-4 transition-all hover:border-dark-border-light"
              >
                <h3 className="text-sm font-medium text-text-primary group-hover:text-status-star transition-colors" dir="rtl">
                  {lang === 'ar' ? person.nameAr : person.nameEn || person.nameAr}
                </h3>
                {(person.birthYear || person.deathYear) && (
                  <p className="mt-1 text-[10px] text-text-muted">
                    {person.birthYear || '?'} — {person.deathYear || '?'}
                  </p>
                )}
                {person.bio && (
                  <p className="mt-1 text-xs text-text-muted line-clamp-2" dir="rtl">{person.bio}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
