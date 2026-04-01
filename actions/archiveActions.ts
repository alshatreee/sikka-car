'use server'

import { prisma } from '@/lib/prisma'
import { auth } from '@clerk/nextjs/server'

// ===== Archive Items =====

export async function getArchiveItems(params: {
  page?: number
  limit?: number
  type?: string
  status?: string
}) {
  const { page = 1, limit = 20, type, status = 'PUBLISHED' } = params
  const skip = (page - 1) * limit

  const where: Record<string, unknown> = { status }
  if (type) where.itemType = type

  const [items, total] = await Promise.all([
    prisma.archiveItem.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip,
      take: limit,
      select: {
        id: true,
        slug: true,
        titleAr: true,
        titleEn: true,
        itemType: true,
        creator: true,
        publicationYear: true,
        coverImageUrl: true,
        thumbnailUrl: true,
        status: true,
      },
    }),
    prisma.archiveItem.count({ where }),
  ])

  return { items, total }
}

export async function getArchiveItemBySlug(slug: string) {
  return prisma.archiveItem.findUnique({
    where: { slug },
    include: {
      files: {
        orderBy: { isPrimary: 'desc' },
      },
      ocrPages: {
        select: { pageNumber: true, ocrStatus: true, confidence: true },
        orderBy: { pageNumber: 'asc' },
      },
      itemPeople: {
        include: {
          person: { select: { nameAr: true, nameEn: true, slug: true } },
        },
      },
      itemSubjects: {
        include: {
          subject: { select: { nameAr: true, nameEn: true, slug: true } },
        },
      },
    },
  })
}

export async function searchArchiveItems(params: {
  q: string
  type?: string
  yearFrom?: number
  yearTo?: number
  creator?: string
  page?: number
  limit?: number
}) {
  const { q, type, yearFrom, yearTo, creator, page = 1, limit = 20 } = params
  const skip = (page - 1) * limit

  const where: Record<string, unknown> = { status: 'PUBLISHED' }

  if (q && q.trim().length >= 2) {
    where.OR = [
      { titleAr: { contains: q.trim(), mode: 'insensitive' } },
      { titleEn: { contains: q.trim(), mode: 'insensitive' } },
      { searchText: { contains: q.trim(), mode: 'insensitive' } },
      { creator: { contains: q.trim(), mode: 'insensitive' } },
    ]
  }

  if (type) where.itemType = type
  if (creator) where.creator = { contains: creator.trim(), mode: 'insensitive' }

  if (yearFrom || yearTo) {
    where.publicationYear = {}
    if (yearFrom) (where.publicationYear as Record<string, number>).gte = yearFrom
    if (yearTo) (where.publicationYear as Record<string, number>).lte = yearTo
  }

  const [items, total] = await Promise.all([
    prisma.archiveItem.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip,
      take: limit,
      select: {
        id: true,
        slug: true,
        titleAr: true,
        titleEn: true,
        itemType: true,
        creator: true,
        publicationYear: true,
        thumbnailUrl: true,
      },
    }),
    prisma.archiveItem.count({ where }),
  ])

  return { items, total }
}

// ===== Admin Actions (require ADMIN role) =====

async function requireAdmin() {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return null

  const user = await prisma.user.findFirst({
    where: { clerkUserId },
    select: { id: true, role: true },
  })

  if (!user || user.role !== 'ADMIN') return null
  return user
}

export async function createArchiveItem(data: {
  slug: string
  titleAr: string
  titleEn?: string
  descriptionAr?: string
  itemType: string
  creator?: string
  contributor?: string
  publisher?: string
  identifier?: string
  sourceReference?: string
  rightsStatement?: string
  publicationYear?: number
  coveragePlace?: string
  coveragePeriod?: string
  collectionName?: string
  kuwaitPeriod?: string
  manuscriptNotes?: string
  verificationStatus?: string
  coverImageUrl?: string
  tags?: string[]
  status?: string
}) {
  const admin = await requireAdmin()
  if (!admin) return { success: false, error: 'صلاحية المدير مطلوبة' }

  try {
    const item = await prisma.archiveItem.create({
      data: {
        userId: admin.id,
        slug: data.slug,
        titleAr: data.titleAr,
        titleEn: data.titleEn || null,
        descriptionAr: data.descriptionAr || null,
        itemType: data.itemType as 'BOOK',
        creator: data.creator || null,
        contributor: data.contributor || null,
        publisher: data.publisher || null,
        identifier: data.identifier || null,
        sourceReference: data.sourceReference || null,
        rightsStatement: data.rightsStatement || null,
        publicationYear: data.publicationYear || null,
        coveragePlace: data.coveragePlace || null,
        coveragePeriod: data.coveragePeriod || null,
        collectionName: data.collectionName || null,
        kuwaitPeriod: data.kuwaitPeriod || null,
        manuscriptNotes: data.manuscriptNotes || null,
        verificationStatus: data.verificationStatus || null,
        coverImageUrl: data.coverImageUrl || null,
        tags: data.tags || [],
        status: (data.status as 'DRAFT') || 'DRAFT',
        searchText: [data.titleAr, data.titleEn, data.descriptionAr, data.creator].filter(Boolean).join(' '),
      },
    })

    return { success: true, id: item.id, slug: item.slug }
  } catch (error) {
    console.error('createArchiveItem error:', error)
    return { success: false, error: 'فشل إنشاء العنصر' }
  }
}

export async function updateArchiveItem(id: string, data: Record<string, unknown>) {
  const admin = await requireAdmin()
  if (!admin) return { success: false, error: 'صلاحية المدير مطلوبة' }

  try {
    await prisma.archiveItem.update({ where: { id }, data })
    return { success: true }
  } catch (error) {
    console.error('updateArchiveItem error:', error)
    return { success: false, error: 'فشل تحديث العنصر' }
  }
}

export async function deleteArchiveItem(id: string) {
  const admin = await requireAdmin()
  if (!admin) return { success: false, error: 'صلاحية المدير مطلوبة' }

  try {
    await prisma.archiveItem.delete({ where: { id } })
    return { success: true }
  } catch (error) {
    console.error('deleteArchiveItem error:', error)
    return { success: false, error: 'فشل حذف العنصر' }
  }
}

export async function publishArchiveItem(id: string) {
  const admin = await requireAdmin()
  if (!admin) return { success: false, error: 'صلاحية المدير مطلوبة' }

  try {
    await prisma.archiveItem.update({
      where: { id },
      data: { status: 'PUBLISHED' },
    })
    return { success: true }
  } catch (error) {
    console.error('publishArchiveItem error:', error)
    return { success: false, error: 'فشل نشر العنصر' }
  }
}

// ===== Collections =====

export async function getArchiveCollections() {
  return prisma.archiveCollection.findMany({
    orderBy: { nameAr: 'asc' },
  })
}

// ===== People =====

export async function getArchivePeople(page = 1, limit = 50) {
  const skip = (page - 1) * limit
  const [people, total] = await Promise.all([
    prisma.archivePerson.findMany({
      orderBy: { nameAr: 'asc' },
      skip,
      take: limit,
    }),
    prisma.archivePerson.count(),
  ])
  return { people, total }
}

// ===== Admin Stats =====

export async function getArchiveStats() {
  const admin = await requireAdmin()
  if (!admin) return null

  const [totalItems, published, draft, totalFiles, ocrCompleted] = await Promise.all([
    prisma.archiveItem.count(),
    prisma.archiveItem.count({ where: { status: 'PUBLISHED' } }),
    prisma.archiveItem.count({ where: { status: 'DRAFT' } }),
    prisma.archiveFile.count(),
    prisma.archiveOcrPage.count({ where: { ocrStatus: 'COMPLETED' } }),
  ])

  return { totalItems, published, draft, totalFiles, ocrCompleted }
}
