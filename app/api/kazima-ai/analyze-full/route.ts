import { NextRequest, NextResponse } from 'next/server'
import { callLLMJson } from '@/lib/kazima-llm'
import { cleanForLLM } from '@/lib/kazima-cleaner'
import {
  ENTITIES_PROMPT,
  RELATIONS_PROMPT,
  TIMELINE_PROMPT,
  CLASSIFICATION_PROMPT,
  type EntitiesResult,
  type RelationsResult,
  type TimelineResult,
  type ClassificationResult,
} from '@/lib/kazima-prompts'

// POST /api/kazima-ai/analyze-full
// Full analysis: entities + relations + timeline + classification (parallel)
export async function POST(request: NextRequest) {
  try {
    const { text } = await request.json()

    if (!text || typeof text !== 'string' || text.trim().length === 0) {
      return NextResponse.json({ error: 'النص مطلوب' }, { status: 400 })
    }

    if (text.length > 50000) {
      return NextResponse.json({ error: 'النص طويل جدًا. الحد الأقصى 50,000 حرف' }, { status: 400 })
    }

    const cleanedText = cleanForLLM(text)

    // Run all 4 extractions in parallel
    const [entities, relations, timeline, classification] = await Promise.all([
      callLLMJson<EntitiesResult>({
        systemPrompt: ENTITIES_PROMPT,
        userPrompt: cleanedText,
      }),
      callLLMJson<RelationsResult>({
        systemPrompt: RELATIONS_PROMPT,
        userPrompt: cleanedText,
      }),
      callLLMJson<TimelineResult>({
        systemPrompt: TIMELINE_PROMPT,
        userPrompt: cleanedText,
      }),
      callLLMJson<ClassificationResult>({
        systemPrompt: CLASSIFICATION_PROMPT,
        userPrompt: cleanedText,
      }),
    ])

    // Build knowledge graph from entities + relations
    const graph = buildGraph(entities, relations)

    return NextResponse.json({
      entities,
      relations,
      timeline,
      classification,
      graph,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error('Kazima Full Analysis Error:', error)
    const message = error instanceof Error ? error.message : 'خطأ غير متوقع'
    return NextResponse.json(
      { error: `خطأ في التحليل الشامل: ${message}` },
      { status: 500 }
    )
  }
}

// Build knowledge graph from extracted data
function buildGraph(entities: EntitiesResult, relations: RelationsResult) {
  const nodes: { id: string; type: string; label: string }[] = []
  const edges: { source: string; target: string; type: string; uncertain?: boolean }[] = []
  const seen = new Set<string>()

  function addNode(id: string, type: string) {
    if (!seen.has(id)) {
      seen.add(id)
      nodes.push({ id, type, label: id })
    }
  }

  for (const person of entities.persons || []) {
    addNode(person, 'person')
  }
  for (const location of entities.locations || []) {
    addNode(location, 'location')
  }
  for (const book of entities.books || []) {
    addNode(book, 'book')
  }
  for (const tribe of entities.tribes || []) {
    addNode(tribe, 'tribe')
  }

  for (const rel of relations.relations || []) {
    addNode(rel.from, 'person')
    addNode(rel.to, 'person')
    edges.push({
      source: rel.from,
      target: rel.to,
      type: rel.type,
      uncertain: rel.uncertain,
    })
  }

  return { nodes, edges }
}
