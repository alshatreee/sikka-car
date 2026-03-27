import { getAdminStats } from '@/actions/adminActions'
import AdminDashboardClient from './AdminDashboardClient'

export default async function AdminPage() {
  const stats = await getAdminStats()
  return <AdminDashboardClient stats={stats} />
}
