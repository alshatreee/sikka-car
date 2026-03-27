import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'أضف سيارتك | Sikka Car',
  description: 'أضف سيارتك للإيجار على سكة كار - أكبر منصة لتأجير السيارات بين الأفراد في الكويت.',
  openGraph: {
    title: 'أضف سيارتك | Sikka Car',
    description: 'List your car for rent on Sikka Car - Kuwait\'s largest peer-to-peer car rental platform.',
  },
}

export default function ListLayout({ children }: { children: React.ReactNode }) {
  return children
}
