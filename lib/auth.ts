import { auth, currentUser } from '@clerk/nextjs/server'
import { prisma } from './prisma'

export async function getOrCreateCurrentUser() {
  const { userId } = auth()
  if (!userId) return null

  let user = await prisma.user.findUnique({
    where: { clerkUserId: userId },
  })

  if (user) return user

  const clerkUser = await currentUser()
  if (!clerkUser?.emailAddresses?.[0]?.emailAddress) {
    throw new Error('تعذر قراءة البريد الإلكتروني من Clerk')
  }

  user = await prisma.user.create({
    data: {
      clerkUserId: userId,
      email: clerkUser.emailAddresses[0].emailAddress,
      fullName:
        [clerkUser.firstName, clerkUser.lastName].filter(Boolean).join(' ') ||
        null,
      phone: clerkUser.phoneNumbers?.[0]?.phoneNumber || null,
    },
  })

  return user
}

export async function requireAdmin() {
  const user = await getOrCreateCurrentUser()
  if (!user || user.role !== 'ADMIN') {
    throw new Error('غير مصرح لك بالوصول')
  }
  return user
}

export async function isAdmin() {
  const user = await getOrCreateCurrentUser()
  return user?.role === 'ADMIN'
}
