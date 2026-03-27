'use server'

import { prisma } from '@/lib/prisma'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { carListingSchema } from '@/lib/validators'
import { revalidatePath } from 'next/cache'

export async function submitCarListing(rawData: unknown) {
  const currentUser = await getOrCreateCurrentUser()

  if (!currentUser) {
    throw new Error('يجب تسجيل الدخول أولاً')
  }

  const parsed = carListingSchema.safeParse(rawData)
  if (!parsed.success) {
    return {
      success: false,
      errors: parsed.error.flatten(),
    }
  }

  const data = parsed.data

  const car = await prisma.car.create({
    data: {
      ownerId: currentUser.id,
      title: data.title,
      year: data.year,
      dailyPrice: data.dailyPrice,
      area: data.area,
      city: data.city,
      origin: data.origin,
      type: data.type,
      category: data.category,
      seats: data.seats,
      transmission: data.transmission,
      smokingPolicy: data.smokingPolicy,
      distancePolicy: data.distancePolicy,
      minAge: data.minAge,
      availabilityText: data.availabilityText,
      notes: data.notes,
      images: data.images,
      documentImages: data.documentImages,
      status: 'PENDING',
    },
  })

  revalidatePath('/dashboard')
  revalidatePath('/browse')

  return {
    success: true,
    carId: car.id,
    message: 'تم إرسال السيارة للإدارة للمراجعة',
  }
}

export async function getApprovedCars(filters?: {
  area?: string
  transmission?: string
  minPrice?: number
  maxPrice?: number
  category?: string
  search?: string
}) {
  const where: Record<string, unknown> = { status: 'APPROVED' as const }

  if (filters?.area) where.area = filters.area
  if (filters?.transmission) where.transmission = filters.transmission
  if (filters?.category) where.category = filters.category

  if (filters?.minPrice || filters?.maxPrice) {
    where.dailyPrice = {}
    if (filters.minPrice)
      (where.dailyPrice as Record<string, number>).gte = filters.minPrice
    if (filters.maxPrice)
      (where.dailyPrice as Record<string, number>).lte = filters.maxPrice
  }

  if (filters?.search) {
    where.OR = [
      { title: { contains: filters.search, mode: 'insensitive' } },
      { brand: { contains: filters.search, mode: 'insensitive' } },
      { model: { contains: filters.search, mode: 'insensitive' } },
    ]
  }

  return prisma.car.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    include: {
      owner: {
        select: {
          fullName: true,
          email: true,
        },
      },
    },
  })
}

export async function getCarById(id: string) {
  return prisma.car.findUnique({
    where: { id },
    include: {
      owner: {
        select: {
          fullName: true,
          email: true,
          phone: true,
        },
      },
      bookings: {
        where: { review: { isNot: null } },
        select: {
          review: {
            select: {
              id: true,
              rating: true,
              comment: true,
              createdAt: true,
            },
          },
          renter: {
            select: { fullName: true },
          },
        },
        orderBy: { createdAt: 'desc' },
        take: 10,
      },
    },
  })
}

export async function updateCarListing(carId: string, rawData: unknown) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) throw new Error('يجب تسجيل الدخول أولاً')

  const car = await prisma.car.findUnique({ where: { id: carId } })
  if (!car || car.ownerId !== currentUser.id) {
    return { success: false, error: 'غير مصرح لك بتعديل هذه السيارة' }
  }

  const parsed = carListingSchema.safeParse(rawData)
  if (!parsed.success) {
    return { success: false, errors: parsed.error.flatten() }
  }

  const data = parsed.data

  await prisma.car.update({
    where: { id: carId },
    data: {
      title: data.title,
      year: data.year,
      dailyPrice: data.dailyPrice,
      area: data.area,
      city: data.city,
      origin: data.origin,
      type: data.type,
      category: data.category,
      seats: data.seats,
      transmission: data.transmission,
      smokingPolicy: data.smokingPolicy,
      distancePolicy: data.distancePolicy,
      minAge: data.minAge,
      availabilityText: data.availabilityText,
      notes: data.notes,
      images: data.images,
      documentImages: data.documentImages,
      status: 'PENDING',
    },
  })

  revalidatePath('/dashboard')
  revalidatePath('/browse')
  return { success: true, message: 'تم تحديث السيارة وإرسالها للمراجعة' }
}

export async function deleteCar(carId: string) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) throw new Error('يجب تسجيل الدخول أولاً')

  const car = await prisma.car.findUnique({
    where: { id: carId },
    include: { bookings: { where: { status: { in: ['APPROVED', 'ACTIVE'] } } } },
  })

  if (!car || car.ownerId !== currentUser.id) {
    return { success: false, error: 'غير مصرح لك بحذف هذه السيارة' }
  }

  if (car.bookings.length > 0) {
    return { success: false, error: 'لا يمكن حذف سيارة عليها حجوزات نشطة' }
  }

  await prisma.car.delete({ where: { id: carId } })

  revalidatePath('/dashboard')
  revalidatePath('/browse')
  return { success: true }
}

export async function getOwnerCars() {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) throw new Error('يجب تسجيل الدخول أولاً')

  return prisma.car.findMany({
    where: { ownerId: currentUser.id },
    orderBy: { createdAt: 'desc' },
    include: {
      bookings: {
        orderBy: { createdAt: 'desc' },
        take: 5,
        include: {
          renter: {
            select: { fullName: true, email: true },
          },
        },
      },
    },
  })
}
