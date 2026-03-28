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

function calculateDays(startDate: Date, endDate: Date) {
  const diffMs = endDate.getTime() - startDate.getTime()
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return days > 0 ? days : 0
}

export async function createBooking(rawData: unknown) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) return { success: false, error: 'يجب تسجيل الدخول أولاً' }

  // Identity verification: require civil ID and driving license
  if (!currentUser.civilId || !currentUser.drivingLicense) {
    return {
      success: false,
      error: 'يرجى إكمال بيانات الهوية المدنية ورخصة القيادة من صفحة الملف الشخصي قبل الحجز',
    }
  }

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

  // Check for date conflicts with existing bookings
  const conflictingBooking = await prisma.booking.findFirst({
    where: {
      carId: data.carId,
      status: { in: ['AWAITING_PAYMENT', 'APPROVED', 'ACTIVE'] },
      startDate: { lt: end },
      endDate: { gt: start },
    },
  })

  if (conflictingBooking) {
    return { success: false, error: 'السيارة محجوزة في هذه الفترة، يرجى اختيار تواريخ أخرى' }
  }

  const totalAmount = Number(car.dailyPrice) * totalDays

  const booking = await prisma.booking.create({
    data: {
      carId: car.id,
      renterId: currentUser.id,
      startDate: start,
      endDate: end,
      pickupTime: data.pickupTime,
      dropoffTime: data.dropoffTime,
      totalDays,
      totalAmount,
      notes: data.notes,
      status: 'AWAITING_PAYMENT',
    },
  })

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

export async function cancelBooking(bookingId: string) {
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

  await prisma.booking.update({
    where: { id: bookingId },
    data: { status: 'CANCELLED' },
  })

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
  return { success: true }
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
