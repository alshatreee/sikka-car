import { getBookingForInspection } from '@/actions/inspectionActions'
import { notFound } from 'next/navigation'
import InspectionClient from './InspectionClient'

export default async function InspectionPage({
  params,
}: {
  params: Promise<{ bookingId: string }>
}) {
  const { bookingId } = await params
  const booking = await getBookingForInspection(bookingId)

  if (!booking) {
    notFound()
  }

  return <InspectionClient booking={booking} />
}
