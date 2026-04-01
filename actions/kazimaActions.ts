'use server'

import { prisma } from '@/lib/prisma'
import { auth } from '@clerk/nextjs/server'
import type { KazimaMode } from '@/lib/kazima-ai'

const VALID_MODES: KazimaMode[] = ['analysis', 'extraction', 'annotation', 'publication', 'media', 'review', 'comparison', 'error-detection', 'manuscript-expert']

// Save an analysis result (requires authentication)
export async function saveKazimaAnalysis(data: {
  mode: KazimaMode
  inputText: string
  result: string
  additionalContext?: string
  title?: string
}) {
  if (!VALID_MODES.includes(data.mode)) {
    return { success: false, error: 'وضع التحليل غير صالح' }
  }

  const { userId: clerkUserId } = auth()
  if (!clerkUserId) {
    return { success: false, error: 'يجب تسجيل الدخول لحفظ التحليلات' }
  }

  try {
    await prisma.kazimaAnalysis.create({
      data: {
        userId: clerkUserId,
        mode: data.mode,
        inputText: data.inputText,
        result: data.result,
        additionalContext: data.additionalContext || null,
        title: data.title || null,
      },
    })

    return { success: true }
  } catch (error) {
    console.error('saveKazimaAnalysis error:', error)
    return { success: false, error: 'فشل حفظ التحليل' }
  }
}

// Get user's saved analyses
export async function getKazimaAnalyses(page = 1, limit = 20) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return { analyses: [], total: 0 }

  const skip = (page - 1) * limit

  const [analyses, total] = await Promise.all([
    prisma.kazimaAnalysis.findMany({
      where: { userId: clerkUserId },
      orderBy: { createdAt: 'desc' },
      skip,
      take: limit,
    }),
    prisma.kazimaAnalysis.count({
      where: { userId: clerkUserId },
    }),
  ])

  return { analyses, total }
}

// Toggle favorite on an analysis
export async function toggleKazimaFavorite(analysisId: string) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return { success: false }

  try {
    const analysis = await prisma.kazimaAnalysis.findFirst({
      where: { id: analysisId, userId: clerkUserId },
    })

    if (!analysis) return { success: false, error: 'التحليل غير موجود' }

    await prisma.kazimaAnalysis.update({
      where: { id: analysisId },
      data: { isFavorite: !analysis.isFavorite },
    })

    return { success: true }
  } catch (error) {
    console.error('toggleKazimaFavorite error:', error)
    return { success: false, error: 'فشل تحديث المفضلة' }
  }
}

// Delete an analysis
export async function deleteKazimaAnalysis(analysisId: string) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return { success: false }

  try {
    await prisma.kazimaAnalysis.deleteMany({
      where: { id: analysisId, userId: clerkUserId },
    })

    return { success: true }
  } catch (error) {
    console.error('deleteKazimaAnalysis error:', error)
    return { success: false, error: 'فشل حذف التحليل' }
  }
}

// Save a manuscript (requires authentication)
export async function saveKazimaManuscript(data: {
  title: string
  author?: string
  period?: string
  tradition?: string
  rawText: string
  notes?: string
  imageUrls?: string[]
  tags?: string[]
}) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) {
    return { success: false, error: 'يجب تسجيل الدخول' }
  }

  try {
    await prisma.kazimaManuscript.create({
      data: {
        userId: clerkUserId,
        title: data.title,
        author: data.author || null,
        period: data.period || null,
        tradition: data.tradition || null,
        rawText: data.rawText,
        notes: data.notes || null,
        imageUrls: data.imageUrls || [],
        tags: data.tags || [],
      },
    })

    return { success: true }
  } catch (error) {
    console.error('saveKazimaManuscript error:', error)
    return { success: false, error: 'فشل حفظ المخطوطة' }
  }
}

// Get user's manuscripts
export async function getKazimaManuscripts() {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return []

  return prisma.kazimaManuscript.findMany({
    where: { userId: clerkUserId },
    orderBy: { createdAt: 'desc' },
  })
}

// ===== Knowledge Base Documents =====

// Add a document to the knowledge base (requires authentication)
export async function addKazimaDocument(data: {
  title: string
  content: string
  source?: string
  author?: string
  period?: string
  region?: string
  category?: string
  tags?: string[]
  metadata?: string
}) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) {
    return { success: false, error: 'يجب تسجيل الدخول' }
  }

  try {
    await prisma.kazimaDocument.create({
      data: {
        userId: clerkUserId,
        title: data.title,
        content: data.content,
        source: data.source || null,
        author: data.author || null,
        period: data.period || null,
        region: data.region || null,
        category: data.category || null,
        tags: data.tags || [],
        metadata: data.metadata || null,
      },
    })

    return { success: true }
  } catch (error) {
    console.error('addKazimaDocument error:', error)
    return { success: false, error: 'فشل إضافة الوثيقة' }
  }
}

// Get documents from knowledge base
export async function getKazimaDocuments(page = 1, limit = 20) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return { documents: [], total: 0 }

  const skip = (page - 1) * limit

  const [documents, total] = await Promise.all([
    prisma.kazimaDocument.findMany({
      where: { userId: clerkUserId },
      orderBy: { createdAt: 'desc' },
      skip,
      take: limit,
      select: {
        id: true,
        title: true,
        source: true,
        author: true,
        category: true,
        tags: true,
        createdAt: true,
      },
    }),
    prisma.kazimaDocument.count({
      where: { userId: clerkUserId },
    }),
  ])

  return { documents, total }
}

// Delete a document
export async function deleteKazimaDocument(documentId: string) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return { success: false }

  try {
    await prisma.kazimaDocument.deleteMany({
      where: { id: documentId, userId: clerkUserId },
    })

    return { success: true }
  } catch (error) {
    console.error('deleteKazimaDocument error:', error)
    return { success: false, error: 'فشل حذف الوثيقة' }
  }
}

// Save graph data from full analysis (requires authentication)
export async function saveKazimaGraph(data: {
  analysisId?: string
  nodesJson: string
  edgesJson: string
  sourceText?: string
}) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) {
    return { success: false, error: 'يجب تسجيل الدخول لحفظ بيانات الشبكة' }
  }

  try {
    await prisma.kazimaGraphData.create({
      data: {
        analysisId: data.analysisId || null,
        nodesJson: data.nodesJson,
        edgesJson: data.edgesJson,
        sourceText: data.sourceText || null,
      },
    })

    return { success: true }
  } catch (error) {
    console.error('saveKazimaGraph error:', error)
    return { success: false, error: 'فشل حفظ بيانات الشبكة' }
  }
}
