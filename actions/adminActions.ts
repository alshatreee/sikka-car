'use server'

import { prisma } from '@/lib/prisma'
import { requireAdmin, getOrCreateCurrentUser } from '@/lib/auth'
import { revalidatePath } from 'next/cache'
import { logAudit } from '@/lib/audit'

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
  const currentUser = await requireAdmin()

  const car = await prisma.car.update({
    where: { id: carId },
    data: { status },
  })

  // Log car approval/rejection (fire-and-forget)
  const action = status === 'APPROVED' ? 'CAR_APPROVED' : 'CAR_REJECTED'
  logAudit({
    userId: currentUser.id,
    action,
    entity: 'Car',
    entityId: carId,
    details: `Status changed to: ${status}`,
  }).catch((err) => console.error(`Failed to log car ${action}:`, err))

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
  const currentUser = await requireAdmin()

  const booking = await prisma.booking.update({
    where: { id: bookingId },
    data: { status },
  })

  // Log booking status change (fire-and-forget)
  logAudit({
    userId: currentUser.id,
    action: 'BOOKING_STATUS_CHANGED',
    entity: 'Booking',
    entityId: bookingId,
    details: `Status changed to: ${status}`,
  }).catch((err) => console.error('Failed to log booking status change:', err))

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
  const currentUser = await requireAdmin()

  // Prevent admin from demoting themselves
  if (userId === currentUser.id && role === 'USER') {
    throw new Error('لا يمكنك تغيير صلاحياتك بنفسك')
  }

  // Prevent removing the last admin
  if (role === 'USER') {
    const adminCount = await prisma.user.count({ where: { role: 'ADMIN' } })
    if (adminCount <= 1) {
      throw new Error('لا يمكن إزالة آخر مشرف')
    }
  }

  const user = await prisma.user.update({
    where: { id: userId },
    data: { role },
  })

  // Log user role change (fire-and-forget)
  logAudit({
    userId: currentUser.id,
    action: 'USER_ROLE_CHANGED',
    entity: 'User',
    entityId: userId,
    details: `Role changed to: ${role}`,
  }).catch((err) => console.error('Failed to log user role change:', err))

  revalidatePath('/admin/users')
  return user
}
