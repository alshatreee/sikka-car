import { getCarById } from '@/actions/carActions'
import { getOrCreateCurrentUser, isAdmin } from '@/lib/auth'
import { notFound } from 'next/navigation'
import CarDetailClient from './CarDetailClient'
import type { Metadata } from 'next'

interface Props {
  params: { id: string }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const car = await getCarById(params.id)
  if (!car) return {}

  return {
    title: `${car.title} - سكة كار`,
    description: `استأجر ${car.title} في ${car.area}، الكويت. ${car.dailyPrice} د.ك / يوم`,
    openGraph: {
      title: `${car.title} - سكة كار`,
      description: `استأجر ${car.title} في ${car.area}، الكويت`,
      images: car.images?.[0] ? [car.images[0]] : [],
    },
  }
}

export default async function CarDetailPage({ params }: Props) {
  const car = await getCarById(params.id)

  const currentUser = await getOrCreateCurrentUser()
  const adminUser = await isAdmin()

  // Allow admins to view any car, but regular users can only see approved cars
  if (!car || (!adminUser && car.status !== 'APPROVED')) {
    notFound()
  }

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: car.title,
    image: car.images,
    description: `${car.title} - ${car.area}، الكويت`,
    brand: car.brand ? { '@type': 'Brand', name: car.brand } : undefined,
    offers: {
      '@type': 'Offer',
      priceCurrency: 'KWD',
      price: String(car.dailyPrice),
      availability: 'https://schema.org/InStock',
      priceSpecification: {
        '@type': 'UnitPriceSpecification',
        price: String(car.dailyPrice),
        priceCurrency: 'KWD',
        unitCode: 'DAY',
      },
    },
    vehicleConfiguration: car.transmission,
    vehicleModelDate: String(car.year),
    numberOfPassengers: car.seats,
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <CarDetailClient
        car={JSON.parse(JSON.stringify(car))}
        currentUser={
          currentUser
            ? { fullName: currentUser.fullName || '', email: currentUser.email }
            : null
        }
      />
    </>
  )
}
