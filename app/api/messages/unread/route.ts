import { getOrCreateCurrentUser } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const user = await getOrCreateCurrentUser()
    if (!user) {
      return NextResponse.json({ count: 0 })
    }

    const count = await prisma.message.count({
      where: {
        receiverId: user.id,
        read: false,
      },
    })

    return NextResponse.json({ count })
  } catch (error) {
    console.error('Failed to get unread count:', error)
    return NextResponse.json({ count: 0 })
  }
}
