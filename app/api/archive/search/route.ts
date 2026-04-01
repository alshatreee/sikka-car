import { NextRequest, NextResponse } from 'next/server'
import { searchArchiveItems } from '@/actions/archiveActions'

// GET /api/archive/search?q=...&type=...&yearFrom=...&yearTo=...&creator=...
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const q = searchParams.get('q') || ''
    const type = searchParams.get('type') || undefined
    const yearFrom = searchParams.get('yearFrom') ? parseInt(searchParams.get('yearFrom')!) : undefined
    const yearTo = searchParams.get('yearTo') ? parseInt(searchParams.get('yearTo')!) : undefined
    const creator = searchParams.get('creator') || undefined
    const page = parseInt(searchParams.get('page') || '1')
    const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100)

    if (!q && !type && !creator) {
      return NextResponse.json({ items: [], total: 0 })
    }

    const result = await searchArchiveItems({ q, type, yearFrom, yearTo, creator, page, limit })
    return NextResponse.json(result)
  } catch (error) {
    console.error('Archive search error:', error)
    return NextResponse.json({ error: 'خطأ في البحث' }, { status: 500 })
  }
}
