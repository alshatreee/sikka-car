import { NextRequest, NextResponse } from 'next/server'
import { KAZIMA_SYSTEM_PROMPT, buildKazimaPrompt, validateKazimaRequest } from '@/lib/kazima-ai'
import { callLLM } from '@/lib/kazima-llm'
import { cleanForLLM } from '@/lib/kazima-cleaner'

// POST /api/kazima-ai
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const validation = validateKazimaRequest(body)

    if (!validation.valid || !validation.data) {
      return NextResponse.json({ error: validation.error }, { status: 400 })
    }

    const { mode, text, additionalContext } = validation.data
    const cleanedText = cleanForLLM(text)
    const userPrompt = buildKazimaPrompt(mode, cleanedText, additionalContext)

    const result = await callLLM({
      systemPrompt: KAZIMA_SYSTEM_PROMPT,
      userPrompt,
    })

    return NextResponse.json({
      mode,
      result,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error('Kazima AI Error:', error)
    const message = error instanceof Error ? error.message : 'خطأ غير متوقع'
    return NextResponse.json(
      { error: `خطأ في معالجة الطلب: ${message}` },
      { status: 500 }
    )
  }
}
