'use server'

import { prisma } from '@/lib/prisma'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { revalidatePath } from 'next/cache'

export async function updateProfile(data: {
  fullName?: string
  phone?: string
  civilId?: string
  drivingLicense?: string
}) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return { success: false, error: 'يجب تسجيل الدخول أولاً' }

  await prisma.user.update({
    where: { id: currentUser.id },
    data: {
      fullName: data.fullName || currentUser.fullName,
      phone: data.phone || currentUser.phone,
      civilId: data.civilId || currentUser.civilId,
      drivingLicense: data.drivingLicense || currentUser.drivingLicense,
    },
  })

  revalidatePath('/profile')
  revalidatePath('/dashboard')
  return { success: true }
}

export async function getProfile() {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return null

  return {
    fullName: currentUser.fullName,
    email: currentUser.email,
    phone: currentUser.phone,
    civilId: currentUser.civilId,
    drivingLicense: currentUser.drivingLicense,
  }
}

export async function uploadBookingPhoto(data: {
  bookingId: string
  url: string
  type: string
  uploadedBy: string
}) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return { success: false, error: 'يجب تسجيل الدخول أولاً' }

  const booking = await prisma.booking.findUnique({
    where: { id: data.bookingId },
    include: { car: true },
  })

  if (!booking) return { success: false, error: 'الحجز غير موجود' }

  // Check authorization: owner, renter, or admin
  const isOwner = booking.car.ownerId === currentUser.id
  const isRenter = booking.renterId === currentUser.id
  const isAdmin = currentUser.role === 'ADMIN'

  if (!isOwner && !isRenter && !isAdmin) {
    return { success: false, error: 'غير مصرح لك برفع الصور' }
  }

  await prisma.bookingPhoto.create({
    data: {
      bookingId: data.bookingId,
      url: data.url,
      type: data.type,
      uploadedBy: data.uploadedBy,
    },
  })

  revalidatePath('/dashboard')
  return { success: true }
}

export async function getBookingPhotos(bookingId: string) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return []

  return prisma.bookingPhoto.findMany({
    where: { bookingId },
    orderBy: { createdAt: 'asc' },
  })
}
