import { NextRequest, NextResponse } from 'next/server'
import { callLLM } from '@/lib/kazima-llm'
import { CHAT_SYSTEM_PROMPT } from '@/lib/kazima-prompts'
import { prisma } from '@/lib/prisma'
import { cleanForSearch } from '@/lib/kazima-cleaner'

// POST /api/kazima-ai/chat
// RAG-style chat: search knowledge base → build context → answer
export async function POST(request: NextRequest) {
  try {
    const { query, conversationHistory } = await request.json()

    if (!query || typeof query !== 'string' || query.trim().length === 0) {
      return NextResponse.json({ error: 'السؤال مطلوب' }, { status: 400 })
    }

    // Search knowledge base for relevant documents
    const normalizedQuery = cleanForSearch(query)
    const searchTerms = normalizedQuery.split(' ').filter((t: string) => t.length > 2)

    // Search in KazimaDocument using text search
    let documents: { title: string; content: string; source: string | null }[] = []

    if (searchTerms.length > 0) {
      // Search across documents using LIKE for each term
      documents = await prisma.kazimaDocument.findMany({
        where: {
          OR: searchTerms.flatMap((term: string) => [
            { content: { contains: term, mode: 'insensitive' as const } },
            { title: { contains: term, mode: 'insensitive' as const } },
            { tags: { has: term } },
          ]),
        },
        select: {
          title: true,
          content: true,
          source: true,
        },
        take: 5,
        orderBy: { createdAt: 'desc' },
      })
    }

    // Also search in saved analyses
    const analyses = await prisma.kazimaAnalysis.findMany({
      where: {
        OR: searchTerms.flatMap((term: string) => [
          { inputText: { contains: term, mode: 'insensitive' as const } },
          { result: { contains: term, mode: 'insensitive' as const } },
        ]),
      },
      select: {
        inputText: true,
        result: true,
        mode: true,
      },
      take: 3,
      orderBy: { createdAt: 'desc' },
    })

    // Build context from results
    let context = ''

    if (documents.length > 0) {
      context += 'مصادر من قاعدة كاظمة المعرفية:\n\n'
      for (const doc of documents) {
        context += `--- ${doc.title} ---\n`
        if (doc.source) context += `المصدر: ${doc.source}\n`
        context += `${doc.content.slice(0, 2000)}\n\n`
      }
    }

    if (analyses.length > 0) {
      context += 'تحليلات سابقة ذات صلة:\n\n'
      for (const a of analyses) {
        context += `[${a.mode}]\n${a.result.slice(0, 1000)}\n\n`
      }
    }

    // Build the prompt
    let userPrompt: string

    if (context) {
      userPrompt = `السياق:\n${context}\n\nالسؤال:\n${query}`
    } else {
      userPrompt = `لا توجد مصادر في قاعدة البيانات حاليًا تتعلق بهذا السؤال.
أجب بناءً على معرفتك العامة، مع التنبيه أن الإجابة ليست من مصادر كاظمة.

السؤال:
${query}`
    }

    // Include conversation history if provided
    if (conversationHistory && Array.isArray(conversationHistory) && conversationHistory.length > 0) {
      const historyStr = conversationHistory
        .slice(-4) // Last 4 exchanges max
        .map((h: { role: string; content: string }) => `${h.role === 'user' ? 'السؤال' : 'الجواب'}: ${h.content}`)
        .join('\n\n')
      userPrompt = `المحادثة السابقة:\n${historyStr}\n\n${userPrompt}`
    }

    const answer = await callLLM({
      systemPrompt: CHAT_SYSTEM_PROMPT,
      userPrompt,
    })

    return NextResponse.json({
      answer,
      sources: documents.map((d) => ({ title: d.title, source: d.source })),
      hasContext: documents.length > 0 || analyses.length > 0,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error('Kazima Chat Error:', error)
    const message = error instanceof Error ? error.message : 'خطأ غير متوقع'
    return NextResponse.json(
      { error: `خطأ في المحادثة: ${message}` },
      { status: 500 }
    )
  }
}
