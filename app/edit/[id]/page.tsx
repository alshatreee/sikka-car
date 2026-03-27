import { getCarById } from '@/actions/carActions'
import { getOrCreateCurrentUser } from '@/lib/auth'
import { notFound, redirect } from 'next/navigation'
import EditCarClient from './EditCarClient'

interface Props {
  params: { id: string }
}

export default async function EditCarPage({ params }: Props) {
  const currentUser = await getOrCreateCurrentUser()
  if (!currentUser) redirect('/sign-in')

  const car = await getCarById(params.id)
  if (!car || car.ownerId !== currentUser.id) notFound()

  return <EditCarClient car={JSON.parse(JSON.stringify(car))} />
}
