import { getCarById } from '@/actions/carActions'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { notFound } from 'next/navigation'
import CarDetailClient from './CarDetailClient'

interface Props {
  params: { id: string }
}

export default async function CarDetailPage({ params }: Props) {
  const car = await getCarById(params.id)

  if (!car || car.status !== 'APPROVED') {
    notFound()
  }

  const currentUser = await getOrCreateCurrentUser()

  return (
    <CarDetailClient
      car={JSON.parse(JSON.stringify(car))}
      currentUser={
        currentUser
          ? { fullName: currentUser.fullName || '', email: currentUser.email }
          : null
      }
    />
  )
}
