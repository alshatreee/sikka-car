'use server'

import { prisma } from '@/lib/prisma'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { revalidatePath } from 'next/cache'

export async function createInspection(
  bookingId: string,
  type: 'PICKUP' | 'RETURN',
  photos: string[],
  notes?: string,
  mileage?: number,
  fuelLevel?: string
) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) {
    return { success: false, error: 'يجب تسجيل الدخول أولاً' }
  }

  // Validate booking exists
  const booking = await prisma.booking.findUnique({
    where: { id: bookingId },
    include: { car: true },
  })

  if (!booking) {
    return { success: false, error: 'الحجز غير موجود' }
  }

  // Check if current user is owner or renter
  const isOwner = booking.car.ownerId === currentUser.id
  const isRenter = booking.renterId === currentUser.id

  if (!isOwner && !isRenter) {
    return { success: false, error: 'غير مصرح لك بتوثيق هذا الحجز' }
  }

  // Validate photos
  if (!photos || photos.length === 0) {
    return { success: false, error: 'يجب إضافة صور التفتيش' }
  }

  try {
    const inspection = await prisma.carInspection.create({
      data: {
        bookingId,
        type,
        photos,
        notes: notes || null,
        mileage: mileage || null,
        fuelLevel: fuelLevel || null,
        createdBy: currentUser.id,
      },
    })

    revalidatePath(`/inspection/${bookingId}`)
    revalidatePath('/dashboard')

    return {
      success: true,
      inspectionId: inspection.id,
    }
  } catch (error) {
    console.error('Failed to create inspection:', error)
    return { success: false, error: 'فشل إنشاء التفتيش' }
  }
}

export async function getInspections(bookingId: string) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) {
    return []
  }

  // Validate booking exists and user has access
  const booking = await prisma.booking.findUnique({
    where: { id: bookingId },
    include: { car: true },
  })

  if (!booking) {
    return []
  }

  const isOwner = booking.car.ownerId === currentUser.id
  const isRenter = booking.renterId === currentUser.id

  if (!isOwner && !isRenter) {
    return []
  }

  return prisma.carInspection.findMany({
    where: { bookingId },
    orderBy: { createdAt: 'asc' },
  })
}

export async function getBookingForInspection(bookingId: string) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) {
    return null
  }

  const booking = await prisma.booking.findUnique({
    where: { id: bookingId },
    include: {
      car: true,
      renter: true,
      inspections: {
        orderBy: { createdAt: 'asc' },
      },
    },
  })

  if (!booking) {
    return null
  }

  // Check if current user is owner or renter
  const isOwner = booking.car.ownerId === currentUser.id
  const isRenter = booking.renterId === currentUser.id

  if (!isOwner && !isRenter) {
    return null
  }

  return booking
}
