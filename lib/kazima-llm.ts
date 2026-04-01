// lib/kazima-llm.ts
// Shared LLM calling utility for Kazima AI

import { KAZIMA_SYSTEM_PROMPT } from './kazima-ai'

interface LLMCallOptions {
  systemPrompt?: string
  userPrompt: string
  jsonMode?: boolean
}

/**
 * Call the configured LLM (Anthropic or OpenAI-compatible)
 * Returns the raw text response
 */
export async function callLLM(options: LLMCallOptions): Promise<string> {
  const { systemPrompt = KAZIMA_SYSTEM_PROMPT, userPrompt, jsonMode = false } = options

  const anthropicKey = process.env.ANTHROPIC_API_KEY
  const openaiKey = process.env.OPENAI_API_KEY
  const openaiBaseUrl = process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1'
  const modelId = process.env.KAZIMA_MODEL_ID

  if (anthropicKey) {
    return callAnthropic(anthropicKey, systemPrompt, userPrompt, modelId)
  } else if (openaiKey) {
    return callOpenAI(openaiKey, openaiBaseUrl, systemPrompt, userPrompt, modelId, jsonMode)
  }

  throw new Error('لم يتم تكوين مفتاح API. أضف ANTHROPIC_API_KEY أو OPENAI_API_KEY في ملف .env')
}

async function callAnthropic(
  apiKey: string,
  systemPrompt: string,
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
      system: systemPrompt,
      messages: [{ role: 'user', content: userPrompt }],
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(`Anthropic API error: ${response.status} - ${JSON.stringify(errorData)}`)
  }

  const data = await response.json()
  return data.content?.[0]?.text || ''
}

async function callOpenAI(
  apiKey: string,
  baseUrl: string,
  systemPrompt: string,
  userPrompt: string,
  modelId?: string,
  jsonMode?: boolean
): Promise<string> {
  const body: Record<string, unknown> = {
    model: modelId || 'gpt-4o',
    max_tokens: 8192,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
  }

  if (jsonMode) {
    body.response_format = { type: 'json_object' }
  }

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(`OpenAI API error: ${response.status} - ${JSON.stringify(errorData)}`)
  }

  const data = await response.json()
  return data.choices?.[0]?.message?.content || ''
}

/**
 * Call LLM and parse JSON response
 */
export async function callLLMJson<T>(options: LLMCallOptions): Promise<T> {
  const text = await callLLM({ ...options, jsonMode: true })

  // Extract JSON from response (handle markdown code blocks)
  const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  const jsonStr = jsonMatch ? jsonMatch[1].trim() : text.trim()

  try {
    return JSON.parse(jsonStr) as T
  } catch {
    // Try to find JSON object in the text
    const objectMatch = jsonStr.match(/\{[\s\S]*\}/)
    if (objectMatch) {
      return JSON.parse(objectMatch[0]) as T
    }
    throw new Error('فشل في تحليل الاستجابة كـ JSON')
  }
}
