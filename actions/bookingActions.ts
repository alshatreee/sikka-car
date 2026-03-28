'use server'

import { prisma } from '@/lib/prisma'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { bookingSchema } from '@/lib/validators'
import { revalidatePath } from 'next/cache'
import {
  sendBookingConfirmation,
  sendBookingNotificationToOwner,
  sendBookingCancellation,
} from '@/lib/email'
import { logAudit } from '@/lib/audit'

function calculateDays(startDate: Date, endDate: Date) {
  const diffMs = endDate.getTime() - startDate.getTime()
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return days > 0 ? days : 0
}

export async function createBooking(rawData: unknown) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return { success: false, error: 'يجب تسجيل الدخول أولاً' }



  const parsed = bookingSchema.safeParse(rawData)
  if (!parsed.success) {
    return {
      success: false,
      errors: parsed.error.flatten(),
    }
  }

  const data = parsed.data
  const car = await prisma.car.findUnique({ where: { id: data.carId } })

  if (!car || car.status !== 'APPROVED') {
    return { success: false, error: 'السيارة غير متاحة للحجز' }
  }

  const start = new Date(data.startDate)
  const end = new Date(data.endDate)
  const totalDays = calculateDays(start, end)

  if (totalDays <= 0) {
    return { success: false, error: 'تاريخ الحجز غير صحيح' }
  }

  const totalAmount = Number(car.dailyPrice) * totalDays

  // Wrap conflict check and creation in a transaction for atomicity
  let booking
  try {
    booking = await prisma.$transaction(async (tx) => {
      const conflictingBooking = await tx.booking.findFirst({
        where: {
          carId: data.carId,
          status: { in: ['AWAITING_PAYMENT', 'APPROVED', 'ACTIVE'] },
          startDate: { lt: end },
          endDate: { gt: start },
        },
      })

      if (conflictingBooking) {
        throw new Error('CONFLICT')
      }

      return tx.booking.create({
        data: {
          carId: car.id,
          renterId: currentUser.id,
          startDate: start,
          endDate: end,
          pickupTime: data.pickupTime,
          dropoffTime: data.dropoffTime,
          civilId: data.civilId || undefined,
          licenseNumber: data.licenseNumber || undefined,
          civilIdImage: data.civilIdImage || undefined,
          licenseImage: data.licenseImage || undefined,
          totalDays,
          totalAmount,
          notes: data.notes,
          status: 'AWAITING_PAYMENT',
        },
      })
    })
  } catch (error: any) {
    if (error?.message === 'CONFLICT') {
      return { success: false, error: 'السيارة محجوزة في هذه الفترة، يرجى اختيار تواريخ أخرى' }
    }
    throw error
  }

  // Log booking creation (fire-and-forget)
  logAudit({
    userId: currentUser.id,
    action: 'BOOKING_CREATED',
    entity: 'Booking',
    entityId: booking.id,
    details: `Car: ${car.title}, Days: ${totalDays}, Amount: ${totalAmount}`,
  }).catch((err) => console.error('Failed to log booking creation:', err))

  // Send emails (fire-and-forget)
  // Send confirmation to renter
  if (currentUser.email) {
    sendBookingConfirmation(currentUser.email, {
      bookingId: booking.id,
      carTitle: car.title,
      startDate: start,
      endDate: end,
      pickupTime: data.pickupTime,
      dropoffTime: data.dropoffTime,
      totalDays,
      totalAmount: Number(totalAmount),
      renterName: currentUser.fullName || 'Guest',
    }).catch((err) => console.error('Failed to send booking confirmation:', err))
  }

  // Send notification to owner
  const owner = await prisma.user.findUnique({
    where: { id: car.ownerId },
    select: { email: true, fullName: true },
  })
  if (owner?.email) {
    sendBookingNotificationToOwner(owner.email, {
      bookingId: booking.id,
      carTitle: car.title,
      startDate: start,
      endDate: end,
      pickupTime: data.pickupTime,
      dropoffTime: data.dropoffTime,
      totalDays,
      totalAmount: Number(totalAmount),
      renterName: currentUser.fullName || 'Guest',
      ownerName: owner.fullName || 'Car Owner',
    }).catch((err) => console.error('Failed to send owner notification:', err))
  }

  revalidatePath('/dashboard')

  return {
    success: true,
    bookingId: booking.id,
    totalAmount,
  }
}

export async function getBookedDates(carId: string) {
  const bookings = await prisma.booking.findMany({
    where: {
      carId,
      status: { in: ['AWAITING_PAYMENT', 'APPROVED', 'ACTIVE'] },
      endDate: { gte: new Date() },
    },
    select: { startDate: true, endDate: true },
    orderBy: { startDate: 'asc' },
  })

  return bookings.map((b) => ({
    start: b.startDate.toISOString().split('T')[0],
    end: b.endDate.toISOString().split('T')[0],
  }))
}

export async function getUserBookings() {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return []

  return prisma.booking.findMany({
    where: { renterId: currentUser.id },
    orderBy: { createdAt: 'desc' },
    include: {
      car: {
        select: {
          title: true,
          images: true,
          dailyPrice: true,
          area: true,
        },
      },
      review: true,
    },
  })
}

export async function cancelBooking(
  bookingId: string,
  cancellationReason?: string
) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return { success: false, error: 'يجب تسجيل الدخول أولاً' }

  const booking = await prisma.booking.findUnique({
    where: { id: bookingId },
    include: {
      car: {
        select: { title: true },
      },
    },
  })

  if (!booking || booking.renterId !== currentUser.id) {
    return { success: false, error: 'غير مصرح لك بإلغاء هذا الحجز' }
  }

  if (['COMPLETED', 'CANCELLED', 'ACTIVE'].includes(booking.status)) {
    return { success: false, error: 'لا يمكن إلغاء هذا الحجز' }
  }

  // Calculate refund percentage based on cancellation policy
  const now = new Date()
  const hoursUntilStart = (booking.startDate.getTime() - now.getTime()) / (1000 * 60 * 60)

  let refundPercentage = 0
  if (hoursUntilStart > 48) {
    refundPercentage = 100 // Free cancellation
  } else if (hoursUntilStart > 24) {
    refundPercentage = 50 // 50% refund
  }
  // else: < 24 hours: No refund (0%)

  await prisma.booking.update({
    where: { id: bookingId },
    data: {
      status: 'CANCELLED',
      cancellationReason: cancellationReason || null,
      cancelledAt: new Date(),
      refundPercentage,
    },
  })

  // Log booking cancellation (fire-and-forget)
  logAudit({
    userId: currentUser.id,
    action: 'BOOKING_CANCELLED',
    entity: 'Booking',
    entityId: booking.id,
    details: `Refund: ${refundPercentage}%, Reason: ${cancellationReason || 'Not provided'}`,
  }).catch((err) => console.error('Failed to log booking cancellation:', err))

  // Send cancellation email (fire-and-forget)
  if (currentUser.email) {
    sendBookingCancellation(currentUser.email, {
      bookingId: booking.id,
      carTitle: booking.car.title,
      startDate: booking.startDate,
      endDate: booking.endDate,
      pickupTime: booking.pickupTime,
      dropoffTime: booking.dropoffTime,
      totalDays: booking.totalDays,
      totalAmount: Number(booking.totalAmount),
      renterName: currentUser.fullName || 'Guest',
    }).catch((err) => console.error('Failed to send cancellation email:', err))
  }

  revalidatePath('/dashboard')
  return { success: true, refundPercentage }
}

export async function submitReview(bookingId: string, rating: number, comment?: string) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return { success: false, error: 'يجب تسجيل الدخول أولاً' }

  const booking = await prisma.booking.findUnique({
    where: { id: bookingId },
    include: { review: true },
  })

  if (!booking || booking.renterId !== currentUser.id) {
    return { success: false, error: 'غير مصرح لك بتقييم هذا الحجز' }
  }

  if (booking.status !== 'COMPLETED') {
    return { success: false, error: 'لا يمكن التقييم إلا بعد اكتمال الرحلة' }
  }

  if (booking.review) {
    return { success: false, error: 'تم التقييم مسبقاً' }
  }

  if (rating < 1 || rating > 5) {
    return { success: false, error: 'التقييم يجب أن يكون بين 1 و 5' }
  }

  await prisma.review.create({
    data: {
      bookingId,
      rating,
      comment: comment || null,
    },
  })

  revalidatePath('/dashboard')
  return { success: true }
}
