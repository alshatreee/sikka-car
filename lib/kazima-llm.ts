// lib/kazima-llm.ts
// Shared LLM calling utility for Kazima AI

import { KAZIMA_SYSTEM_PROMPT } from './kazima-ai'

interface LLMCallOptions {
  systemPrompt?: string
  userPrompt: string
  jsonMode?: boolean
}

const DEFAULT_ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'
const DEFAULT_OPENAI_MODEL = 'gpt-4o'
const MAX_TOKENS = 8192

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
      model: modelId || DEFAULT_ANTHROPIC_MODEL,
      max_tokens: MAX_TOKENS,
      system: systemPrompt,
      messages: [{ role: 'user', content: userPrompt }],
    }),
  })

  if (!response.ok) {
    const status = response.status
    // Don't expose API error details to client
    throw new Error(`خطأ من خدمة Anthropic (${status})`)
  }

  const data = await response.json()
  const text = data.content?.[0]?.text

  if (!text) {
    throw new Error('لم يُرجع النموذج أي نص')
  }

  return text
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
    model: modelId || DEFAULT_OPENAI_MODEL,
    max_tokens: MAX_TOKENS,
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
    const status = response.status
    throw new Error(`خطأ من خدمة OpenAI (${status})`)
  }

  const data = await response.json()
  const text = data.choices?.[0]?.message?.content

  if (!text) {
    throw new Error('لم يُرجع النموذج أي نص')
  }

  return text
}

/**
 * Call LLM and parse JSON response.
 * Handles: raw JSON, JSON inside markdown code blocks, JSON embedded in text.
 */
export async function callLLMJson<T>(options: LLMCallOptions): Promise<T> {
  const text = await callLLM({ ...options, jsonMode: true })

  // Strategy 1: Try parsing raw text directly
  try {
    return JSON.parse(text) as T
  } catch {
    // Continue to fallback strategies
  }

  // Strategy 2: Extract from markdown code block ```json ... ```
  const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (codeBlockMatch) {
    try {
      return JSON.parse(codeBlockMatch[1].trim()) as T
    } catch {
      // Continue
    }
  }

  // Strategy 3: Find first complete JSON object { ... }
  // Use balanced brace matching instead of greedy regex
  const firstBrace = text.indexOf('{')
  if (firstBrace !== -1) {
    let depth = 0
    let inString = false
    let escape = false

    for (let i = firstBrace; i < text.length; i++) {
      const ch = text[i]

      if (escape) {
        escape = false
        continue
      }

      if (ch === '\\' && inString) {
        escape = true
        continue
      }

      if (ch === '"') {
        inString = !inString
        continue
      }

      if (!inString) {
        if (ch === '{') depth++
        else if (ch === '}') {
          depth--
          if (depth === 0) {
            const jsonCandidate = text.slice(firstBrace, i + 1)
            try {
              return JSON.parse(jsonCandidate) as T
            } catch {
              break
            }
          }
        }
      }
    }
  }

  throw new Error('فشل في تحليل استجابة النموذج كـ JSON. تأكد أن البرومبت يطلب JSON صريحًا.')
}
