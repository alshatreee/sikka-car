'use server'

import { prisma } from '@/lib/prisma'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { bookingSchema } from '@/lib/validators'
import { revalidatePath } from 'next/cache'

function calculateDays(startDate: Date, endDate: Date) {
  const diffMs = endDate.getTime() - startDate.getTime()
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return days > 0 ? days : 0
}

export async function createBooking(rawData: unknown) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) throw new Error('يجب تسجيل الدخول أولاً')

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

  revalidatePath('/dashboard')

  return {
    success: true,
    bookingId: booking.id,
    totalAmount,
  }
}

export async function getUserBookings() {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) throw new Error('يجب تسجيل الدخول أولاً')

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
    },
  })
}
