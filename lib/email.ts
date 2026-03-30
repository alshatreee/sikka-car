import { Resend } from 'resend'


const resendApiKey = process.env.RESEND_API_KEY
const resend = resendApiKey ? new Resend(resendApiKey) : null
const FROM_EMAIL = 'Sikka Car <noreply@sikkacar.com>'


function isEmailEnabled(): boolean {
  if (!resend) {
    console.warn('⚠️ RESEND_API_KEY not set — skipping email')
    return false
  }
  return true
}


interface BookingDetails {
  bookingId: string
  carTitle: string
  startDate: Date
  endDate: Date
  pickupTime?: string | null
  dropoffTime?: string | null
  totalDays: number
  totalAmount: number
  renterName: string
  ownerName?: string
}


interface PaymentDetails {
  bookingId: string
  carTitle: string
  totalAmount: number
  renterName: string
  paymentReference?: string
}


// Email template helpers
