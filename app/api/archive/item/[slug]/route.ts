import { NextRequest, NextResponse } from 'next/server'
import { getArchiveItemBySlug, updateArchiveItem, deleteArchiveItem } from '@/actions/archiveActions'

// GET /api/archive/item/[slug]
export async function GET(
  _request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    const item = await getArchiveItemBySlug(params.slug)

    if (!item) {
      return NextResponse.json({ error: 'العنصر غير موجود' }, { status: 404 })
    }

    return NextResponse.json(item)
  } catch (error) {
    console.error('Archive item error:', error)
    return NextResponse.json({ error: 'خطأ في تحميل العنصر' }, { status: 500 })
  }
}

// PUT /api/archive/item/[slug] — update (ADMIN)
export async function PUT(
  request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    const item = await getArchiveItemBySlug(params.slug)
    if (!item) {
      return NextResponse.json({ error: 'العنصر غير موجود' }, { status: 404 })
    }

    const body = await request.json()
    const result = await updateArchiveItem(item.id, body)

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 403 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Archive update error:', error)
    return NextResponse.json({ error: 'خطأ في التحديث' }, { status: 500 })
  }
}

// DELETE /api/archive/item/[slug] (ADMIN)
export async function DELETE(
  _request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    const item = await getArchiveItemBySlug(params.slug)
    if (!item) {
      return NextResponse.json({ error: 'العنصر غير موجود' }, { status: 404 })
    }

    const result = await deleteArchiveItem(item.id)

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 403 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Archive delete error:', error)
    return NextResponse.json({ error: 'خطأ في الحذف' }, { status: 500 })
  }
}
