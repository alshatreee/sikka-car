import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'تواصل معنا | Sikka Car',
  description: 'تواصل مع فريق سكة كار - بريد إلكتروني، هاتف، أو نموذج تواصل. نرد عليك بأسرع وقت.',
  openGraph: {
    title: 'تواصل معنا | Sikka Car',
    description: 'Contact Sikka Car team - email, phone, or contact form.',
  },
}

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children
}
