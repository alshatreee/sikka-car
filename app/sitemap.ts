import { prisma } from '@/lib/prisma'
import { MetadataRoute } from 'next'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const cars = await prisma.car.findMany({
    where: { status: 'APPROVED' },
    select: { id: true, updatedAt: true },
  })

  const carPages = cars.map((car) => ({
    url: `https://sikkacar.com/cars/${car.id}`,
    lastModified: car.updatedAt,
    changeFrequency: 'weekly' as const,
    priority: 0.8,
  }))

  return [
    {
      url: 'https://sikkacar.com',
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: 'https://sikkacar.com/browse',
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: 'https://sikkacar.com/contact',
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.5,
    },
    ...carPages,
  ]
}
