import { NextRequest, NextResponse } from 'next/server'
import { getArchiveItems, createArchiveItem } from '@/actions/archiveActions'

// GET /api/archive?page=1&limit=20&type=BOOK
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const page = parseInt(searchParams.get('page') || '1')
    const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100)
    const type = searchParams.get('type') || undefined

    const result = await getArchiveItems({ page, limit, type })
    return NextResponse.json(result)
  } catch (error) {
    console.error('Archive browse error:', error)
    return NextResponse.json({ error: 'خطأ في تحميل الأرشيف' }, { status: 500 })
  }
}

// POST /api/archive — create new item (ADMIN)
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    if (!body.titleAr || !body.slug || !body.itemType) {
      return NextResponse.json(
        { error: 'العنوان والـ slug ونوع العنصر مطلوبة' },
        { status: 400 }
      )
    }

    const result = await createArchiveItem(body)

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 403 })
    }

    return NextResponse.json(result, { status: 201 })
  } catch (error) {
    console.error('Archive create error:', error)
    return NextResponse.json({ error: 'خطأ في إنشاء العنصر' }, { status: 500 })
  }
}
