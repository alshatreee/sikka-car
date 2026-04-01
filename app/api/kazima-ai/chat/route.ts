import { NextRequest, NextResponse } from 'next/server'
import { callLLM } from '@/lib/kazima-llm'
import { CHAT_SYSTEM_PROMPT } from '@/lib/kazima-prompts'
import { prisma } from '@/lib/prisma'
import { cleanForSearch } from '@/lib/kazima-cleaner'

// POST /api/kazima-ai/chat
// RAG-style chat: search knowledge base → build context → answer
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const query = typeof body?.query === 'string' ? body.query.trim() : ''
    const conversationHistory = Array.isArray(body?.conversationHistory) ? body.conversationHistory : []

    if (!query) {
      return NextResponse.json({ error: 'السؤال مطلوب' }, { status: 400 })
    }

    if (query.length > 5000) {
      return NextResponse.json({ error: 'السؤال طويل جدًا' }, { status: 400 })
    }

    // Sanitize and extract search terms (min 2 chars, max 10 terms)
    const normalizedQuery = cleanForSearch(query)
    const searchTerms = normalizedQuery
      .split(' ')
      .filter((t: string) => t.length >= 2)
      .slice(0, 10)

    // Search knowledge base for relevant documents
    let documents: { title: string; content: string; source: string | null }[] = []
    let analyses: { inputText: string; result: string; mode: string }[] = []

    if (searchTerms.length > 0) {
      try {
        documents = await prisma.kazimaDocument.findMany({
          where: {
            OR: searchTerms.flatMap((term: string) => [
              { content: { contains: term, mode: 'insensitive' as const } },
              { title: { contains: term, mode: 'insensitive' as const } },
            ]),
          },
          select: { title: true, content: true, source: true },
          take: 5,
          orderBy: { createdAt: 'desc' },
        })

        analyses = await prisma.kazimaAnalysis.findMany({
          where: {
            OR: searchTerms.flatMap((term: string) => [
              { inputText: { contains: term, mode: 'insensitive' as const } },
              { result: { contains: term, mode: 'insensitive' as const } },
            ]),
          },
          select: { inputText: true, result: true, mode: true },
          take: 3,
          orderBy: { createdAt: 'desc' },
        })
      } catch (dbError) {
        // If DB search fails (e.g. tables not migrated yet), continue without context
        console.error('Kazima Chat DB search error:', dbError)
      }
    }

    // Build context from results
    const contextParts: string[] = []

    if (documents.length > 0) {
      contextParts.push('مصادر من قاعدة كاظمة المعرفية:\n')
      for (const doc of documents) {
        contextParts.push(`--- ${doc.title} ---`)
        if (doc.source) contextParts.push(`المصدر: ${doc.source}`)
        contextParts.push(doc.content.slice(0, 2000))
        contextParts.push('')
      }
    }

    if (analyses.length > 0) {
      contextParts.push('تحليلات سابقة ذات صلة:\n')
      for (const a of analyses) {
        contextParts.push(`[${a.mode}] ${a.result.slice(0, 1000)}`)
        contextParts.push('')
      }
    }

    const hasContext = contextParts.length > 0
    const context = contextParts.join('\n')

    // Build the prompt
    let userPrompt: string

    if (hasContext) {
      userPrompt = `السياق:\n${context}\n\nالسؤال:\n${query}`
    } else {
      userPrompt = `ملاحظة: لا توجد مصادر في قاعدة البيانات حاليًا تتعلق بهذا السؤال.
أجب بناءً على معرفتك العامة، مع التنبيه بوضوح أن الإجابة ليست من مصادر كاظمة المحققة.

السؤال:
${query}`
    }

    // Include recent conversation history (last 4 exchanges max)
    if (conversationHistory.length > 0) {
      const validHistory = conversationHistory
        .filter((h: unknown): h is { role: string; content: string } =>
          typeof h === 'object' && h !== null &&
          typeof (h as Record<string, unknown>).role === 'string' &&
          typeof (h as Record<string, unknown>).content === 'string'
        )
        .slice(-4)

      if (validHistory.length > 0) {
        const historyStr = validHistory
          .map((h) => `${h.role === 'user' ? 'السؤال' : 'الجواب'}: ${h.content.slice(0, 500)}`)
          .join('\n\n')
        userPrompt = `المحادثة السابقة:\n${historyStr}\n\n${userPrompt}`
      }
    }

    const answer = await callLLM({
      systemPrompt: CHAT_SYSTEM_PROMPT,
      userPrompt,
    })

    return NextResponse.json({
      answer,
      sources: documents.map((d) => ({ title: d.title, source: d.source })),
      hasContext,
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
