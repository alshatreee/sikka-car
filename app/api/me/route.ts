import { getOrCreateCurrentUser } from '@/lib/auth'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const user = await getOrCreateCurrentUser()
    if (!user) {
      return NextResponse.json({ role: 'GUEST' })
    }
    return NextResponse.json({ role: user.role })
  } catch {
    return NextResponse.json({ role: 'GUEST' })
  }
}
