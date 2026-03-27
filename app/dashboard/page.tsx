import { getOwnerCars } from '@/actions/carActions'
import { getUserBookings } from '@/actions/bookingActions'
import DashboardClient from './DashboardClient'

export default async function DashboardPage() {
  const [cars, bookings] = await Promise.all([
    getOwnerCars(),
    getUserBookings(),
  ])

  return (
    <DashboardClient
      cars={JSON.parse(JSON.stringify(cars))}
      bookings={JSON.parse(JSON.stringify(bookings))}
    />
  )
}
