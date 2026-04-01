import { NextRequest, NextResponse } from 'next/server'
import {
  KAZIMA_SYSTEM_PROMPT,
  buildKazimaPrompt,
  validateKazimaRequest,
} from '@/lib/kazima-ai'

// POST /api/kazima-ai
// Supports both Anthropic Claude API and OpenAI-compatible APIs
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const validation = validateKazimaRequest(body)

    if (!validation.valid || !validation.data) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      )
    }

    const { mode, text, additionalContext } = validation.data
    const userPrompt = buildKazimaPrompt(mode, text, additionalContext)

    // Determine which API to use
    const anthropicKey = process.env.ANTHROPIC_API_KEY
    const openaiKey = process.env.OPENAI_API_KEY
    const openaiBaseUrl = process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1'
    const modelId = process.env.KAZIMA_MODEL_ID

    let result: string

    if (anthropicKey) {
      result = await callAnthropicAPI(anthropicKey, userPrompt, modelId)
    } else if (openaiKey) {
      result = await callOpenAICompatibleAPI(openaiKey, openaiBaseUrl, userPrompt, modelId)
    } else {
      return NextResponse.json(
        { error: 'لم يتم تكوين مفتاح API. أضف ANTHROPIC_API_KEY أو OPENAI_API_KEY في ملف .env' },
        { status: 500 }
      )
    }

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

// Anthropic Claude API
async function callAnthropicAPI(
  apiKey: string,
  userPrompt: string,
  modelId?: string
): Promise<string> {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: modelId || 'claude-sonnet-4-20250514',
      max_tokens: 8192,
      system: KAZIMA_SYSTEM_PROMPT,
      messages: [
        {
          role: 'user',
          content: userPrompt,
        },
      ],
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(
      `Anthropic API error: ${response.status} - ${JSON.stringify(errorData)}`
    )
  }

  const data = await response.json()
  return data.content?.[0]?.text || 'لم يتم إرجاع نتيجة'
}

// OpenAI-compatible API (OpenAI, local models, etc.)
async function callOpenAICompatibleAPI(
  apiKey: string,
  baseUrl: string,
  userPrompt: string,
  modelId?: string
): Promise<string> {
  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: modelId || 'gpt-4o',
      max_tokens: 8192,
      messages: [
        {
          role: 'system',
          content: KAZIMA_SYSTEM_PROMPT,
        },
        {
          role: 'user',
          content: userPrompt,
        },
      ],
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(
      `OpenAI API error: ${response.status} - ${JSON.stringify(errorData)}`
    )
  }

  const data = await response.json()
  return data.choices?.[0]?.message?.content || 'لم يتم إرجاع نتيجة'
}
