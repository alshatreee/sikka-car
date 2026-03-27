import { getAdminUsers } from '@/actions/adminActions'
import AdminUsersClient from './AdminUsersClient'

export default async function AdminUsersPage() {
  const users = await getAdminUsers()
  return <AdminUsersClient users={JSON.parse(JSON.stringify(users))} />
}
