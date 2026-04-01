'use server'

import { prisma } from '@/lib/prisma'
import { auth } from '@clerk/nextjs/server'
import type { KazimaMode } from '@/lib/kazima-ai'

// Save an analysis result
export async function saveKazimaAnalysis(data: {
  mode: KazimaMode
  inputText: string
  result: string
  additionalContext?: string
  title?: string
}) {
  const { userId: clerkUserId } = auth()

  await prisma.kazimaAnalysis.create({
    data: {
      userId: clerkUserId || null,
      mode: data.mode,
      inputText: data.inputText,
      result: data.result,
      additionalContext: data.additionalContext || null,
      title: data.title || null,
    },
  })

  return { success: true }
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

  const analysis = await prisma.kazimaAnalysis.findFirst({
    where: { id: analysisId, userId: clerkUserId },
  })

  if (!analysis) return { success: false }

  await prisma.kazimaAnalysis.update({
    where: { id: analysisId },
    data: { isFavorite: !analysis.isFavorite },
  })

  return { success: true }
}

// Delete an analysis
export async function deleteKazimaAnalysis(analysisId: string) {
  const { userId: clerkUserId } = auth()
  if (!clerkUserId) return { success: false }

  await prisma.kazimaAnalysis.deleteMany({
    where: { id: analysisId, userId: clerkUserId },
  })

  return { success: true }
}

// Save a manuscript
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

  await prisma.kazimaManuscript.create({
    data: {
      userId: clerkUserId || null,
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
