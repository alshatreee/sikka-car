import { getAdminCars } from '@/actions/adminActions'
import AdminCarsClient from './AdminCarsClient'

export default async function AdminCarsPage() {
  const cars = await getAdminCars()
  return <AdminCarsClient cars={JSON.parse(JSON.stringify(cars))} />
}
