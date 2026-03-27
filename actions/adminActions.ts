'use server'

import { prisma } from '@/lib/prisma'
import { requireAdmin } from '@/lib/auth'
import { revalidatePath } from 'next/cache'

// ==================== STATS ====================

export async function getAdminStats() {
  await requireAdmin()

  const [
    totalUsers,
    totalCars,
    pendingCars,
    approvedCars,
    rejectedCars,
    totalBookings,
    activeBookings,
    revenueResult,
  ] = await Promise.all([
    prisma.user.count(),
    prisma.car.count(),
    prisma.car.count({ where: { status: 'PENDING' } }),
    prisma.car.count({ where: { status: 'APPROVED' } }),
    prisma.car.count({ where: { status: 'REJECTED' } }),
    prisma.booking.count(),
    prisma.booking.count({ where: { status: { in: ['APPROVED', 'ACTIVE'] } } }),
    prisma.booking.aggregate({ _sum: { totalAmount: true }, where: { status: { in: ['APPROVED', 'ACTIVE', 'COMPLETED'] } } }),
  ])

  return {
    totalUsers,
    totalCars,
    pendingCars,
    approvedCars,
    rejectedCars,
    totalBookings,
    activeBookings,
    totalRevenue: Number(revenueResult._sum.totalAmount || 0),
  }
}

// ==================== CARS ====================

export async function getAdminCars(status?: string) {
  await requireAdmin()

  const where = status ? { status: status as 'PENDING' | 'APPROVED' | 'REJECTED' } : {}

  return prisma.car.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    include: {
      owner: {
        select: { fullName: true, email: true, phone: true },
      },
      _count: { select: { bookings: true } },
    },
  })
}

export async function updateCarStatus(carId: string, status: 'APPROVED' | 'REJECTED') {
  await requireAdmin()

  const car = await prisma.car.update({
    where: { id: carId },
    data: { status },
  })

  revalidatePath('/admin/cars')
  revalidatePath('/admin')
  revalidatePath('/browse')

  return car
}

// ==================== BOOKINGS ====================

export async function getAdminBookings() {
  await requireAdmin()

  return prisma.booking.findMany({
    orderBy: { createdAt: 'desc' },
    include: {
      car: {
        select: { title: true, images: true, area: true, dailyPrice: true },
      },
      renter: {
        select: { fullName: true, email: true, phone: true },
      },
    },
  })
}

export async function updateBookingStatus(
  bookingId: string,
  status: 'APPROVED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | 'REJECTED'
) {
  await requireAdmin()

  const booking = await prisma.booking.update({
    where: { id: bookingId },
    data: { status },
  })

  revalidatePath('/admin/bookings')
  revalidatePath('/admin')
  revalidatePath('/dashboard')

  return booking
}

// ==================== USERS ====================

export async function getAdminUsers() {
  await requireAdmin()

  return prisma.user.findMany({
    orderBy: { createdAt: 'desc' },
    include: {
      _count: {
        select: { cars: true, bookings: true },
      },
    },
  })
}

export async function updateUserRole(userId: string, role: 'USER' | 'ADMIN') {
  await requireAdmin()

  const user = await prisma.user.update({
    where: { id: userId },
    data: { role },
  })

  revalidatePath('/admin/users')
  return user
}
