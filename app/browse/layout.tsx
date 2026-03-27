import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'تصفح السيارات | Sikka Car',
  description: 'تصفح واستأجر سيارات في الكويت - العاصمة، حولي، الفروانية، الأحمدي، الجهراء. أسعار تبدأ من 5 د.ك يومياً.',
  openGraph: {
    title: 'تصفح السيارات | Sikka Car',
    description: 'Browse and rent cars in Kuwait. Daily prices starting from 5 KWD.',
  },
}

export default function BrowseLayout({ children }: { children: React.ReactNode }) {
  return children
}
