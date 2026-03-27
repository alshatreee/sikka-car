import { getAdminBookings } from '@/actions/adminActions'
import AdminBookingsClient from './AdminBookingsClient'

export default async function AdminBookingsPage() {
  const bookings = await getAdminBookings()
  return <AdminBookingsClient bookings={JSON.parse(JSON.stringify(bookings))} />
}
