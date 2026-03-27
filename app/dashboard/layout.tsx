import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'لوحة التحكم | Sikka Car',
  description: 'إدارة سياراتك وحجوزاتك على سكة كار.',
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children
}
