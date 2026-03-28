import { getOrCreateCurrentUser } from '@/lib/auth'
import { redirect } from 'next/navigation'
import MessagesClient from './MessagesClient'

export const metadata = {
  title: 'Messages',
}

export default async function MessagesPage() {
  const user = await getOrCreateCurrentUser()
  if (!user) {
    redirect('/sign-in')
  }

  return (
    <div className="container mx-auto">
      <MessagesClient />
    </div>
  )
}
