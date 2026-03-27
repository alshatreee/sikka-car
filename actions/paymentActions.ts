'use server'

import { prisma } from '@/lib/prisma'
import { sendPaymentConfirmation } from '@/lib/email'

export async function initiatePayment(
  amount: number,
  bookingId: string,
  customerName: string,
  customerEmail: string
) {
  try {
    const tapSecretKey = process.env.TAP_SECRET_KEY
    const appUrl = process.env.NEXT_PUBLIC_APP_URL

    if (!tapSecretKey || !appUrl) {
      throw new Error('Tap environment variables are missing')
    }

    const res = await fetch('https://api.tap.company/v2/charges', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${tapSecretKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        amount,
        currency: 'KWD',
        customer: {
          first_name: customerName,
          email: customerEmail,
        },
        source: { id: 'src_all' },
        redirect: {
          url: `${appUrl}/payment-success?bookingId=${bookingId}`,
        },
      }),
    })

    const data = await res.json()

    if (data?.transaction?.url) {
      await prisma.booking.update({
        where: { id: bookingId },
        data: {
          paymentReference: data.id ?? null,
          paymentUrl: data.transaction.url,
        },
      })

      return {
        success: true,
        checkoutUrl: data.transaction.url,
      }
    }

    return {
      success: false,
      error: 'حدث خطأ في إنشاء رابط الدفع',
    }
  } catch (error) {
    console.error('Payment error:', error)
    return {
      success: false,
      error: 'فشل الاتصال ببوابة الدفع',
    }
  }
}

export async function verifyPayment(bookingId: string, tapId: string) {
  try {
    const tapSecretKey = process.env.TAP_SECRET_KEY
    if (!tapSecretKey) throw new Error('TAP_SECRET_KEY is missing')

    const res = await fetch(`https://api.tap.company/v2/charges/${tapId}`, {
      headers: {
        Authorization: `Bearer ${tapSecretKey}`,
      },
    })

    const data = await res.json()

    if (data?.status === 'CAPTURED') {
      // Fetch booking with related data for email
      const booking = await prisma.booking.findUnique({
        where: { id: bookingId },
        include: {
          renter: {
            select: { email: true, fullName: true },
          },
          car: {
            select: { title: true },
          },
        },
      })

      await prisma.booking.update({
        where: { id: bookingId },
        data: {
          status: 'APPROVED',
          paymentReference: tapId,
        },
      })

      // Send payment confirmation email (fire-and-forget)
      if (booking?.renter?.email) {
        sendPaymentConfirmation(booking.renter.email, {
          bookingId,
          carTitle: booking.car.title,
          totalAmount: Number(booking.totalAmount),
          renterName: booking.renter.fullName || 'Guest',
          paymentReference: tapId,
        }).catch((err) => console.error('Failed to send payment confirmation:', err))
      }

      return { success: true, status: 'CAPTURED' }
    }

    return { success: false, status: data?.status || 'UNKNOWN' }
  } catch (error) {
    console.error('Payment verification error:', error)
    return { success: false, error: 'فشل التحقق من الدفع' }
  }
}
