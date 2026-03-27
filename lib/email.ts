import { Resend } from 'resend'

const resendApiKey = process.env.RESEND_API_KEY
const resend = resendApiKey ? new Resend(resendApiKey) : null
const FROM_EMAIL = 'onboarding@resend.dev'

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
function getEmailTemplate(title: string, arabicContent: string, englishContent: string) {
  return `
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      line-height: 1.6;
      color: #333;
      margin: 0;
      padding: 0;
      background-color: #f5f5f5;
    }
    .container {
      max-width: 600px;
      margin: 20px auto;
      background-color: #1a1a1a;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .header {
      background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
      padding: 30px 20px;
      text-align: center;
      border-bottom: 3px solid #FFB800;
    }
    .logo {
      font-size: 28px;
      font-weight: bold;
      color: #FFB800;
      margin: 0;
      letter-spacing: 1px;
    }
    .logo-sub {
      font-size: 12px;
      color: #999;
      margin-top: 5px;
    }
    .content {
      padding: 30px 20px;
      color: #f0f0f0;
    }
    .section {
      margin-bottom: 25px;
    }
    .section-title {
      font-size: 18px;
      font-weight: bold;
      color: #FFB800;
      margin-bottom: 12px;
      border-bottom: 2px solid #FFB800;
      padding-bottom: 8px;
    }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid #333;
    }
    .detail-label {
      font-weight: 600;
      color: #FFB800;
      flex: 1;
    }
    .detail-value {
      flex: 1;
      text-align: left;
      color: #ddd;
    }
    .footer {
      background-color: #0a0a0a;
      padding: 20px;
      text-align: center;
      border-top: 1px solid #333;
      font-size: 12px;
      color: #999;
    }
    .footer-text {
      margin: 5px 0;
    }
    .cta-button {
      display: inline-block;
      padding: 12px 30px;
      background-color: #FFB800;
      color: #1a1a1a;
      text-decoration: none;
      border-radius: 4px;
      font-weight: bold;
      margin-top: 15px;
    }
    .language-divider {
      border-top: 2px solid #333;
      margin: 30px 0;
      padding-top: 20px;
    }
    .english-content {
      direction: ltr;
      text-align: left;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">سكا</div>
      <div class="logo-sub">Sikka Car Rental</div>
    </div>

    <div class="content">
      <div>${arabicContent}</div>

      <div class="language-divider"></div>

      <div class="english-content">
        ${englishContent}
      </div>
    </div>

    <div class="footer">
      <div class="footer-text">&copy; 2024 Sikka Car Rental. جميع الحقوق محفوظة</div>
      <div class="footer-text">All rights reserved | سكا لتأجير السيارات</div>
    </div>
  </div>
</body>
</html>
  `.trim()
}

export async function sendBookingConfirmation(to: string, details: BookingDetails) {
  if (!isEmailEnabled()) return

  const startDateStr = details.startDate.toLocaleDateString('ar-SA')
  const endDateStr = details.endDate.toLocaleDateString('ar-SA')
  const amountStr = details.totalAmount.toFixed(2)

  const arabicContent = `
    <div class="section">
      <div class="section-title">تأكيد الحجز</div>
      <p>شكراً ${details.renterName} على حجز سيارتك مع سكا!</p>
      <p>تم استلام طلب الحجز الخاص بك بنجاح. يرجى الانتقال إلى صفحة الدفع لإكمال عملية الدفع.</p>
    </div>

    <div class="section">
      <div class="section-title">تفاصيل الحجز</div>
      <div class="detail-row">
        <span class="detail-label">رقم الحجز:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">السيارة:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">تاريخ الاستلام:</span>
        <span class="detail-value">${startDateStr}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">تاريخ التسليم:</span>
        <span class="detail-value">${endDateStr}</span>
      </div>
      ${details.pickupTime ? `
      <div class="detail-row">
        <span class="detail-label">وقت الاستلام:</span>
        <span class="detail-value">${details.pickupTime}</span>
      </div>
      ` : ''}
      ${details.dropoffTime ? `
      <div class="detail-row">
        <span class="detail-label">وقت التسليم:</span>
        <span class="detail-value">${details.dropoffTime}</span>
      </div>
      ` : ''}
      <div class="detail-row">
        <span class="detail-label">عدد الأيام:</span>
        <span class="detail-value">${details.totalDays}</span>
      </div>
      <div class="detail-row" style="border: none; padding-top: 15px; margin-top: 10px; border-top: 2px solid #FFB800;">
        <span class="detail-label" style="font-size: 18px;">المبلغ الإجمالي:</span>
        <span class="detail-value" style="font-size: 18px; color: #FFB800;">${amountStr} د.ك</span>
      </div>
    </div>

    <div class="section">
      <p>إذا كان لديك أي استفسارات، يرجى التواصل معنا عبر البريد الإلكتروني أو الهاتف.</p>
    </div>
  `

  const englishContent = `
    <div class="section">
      <div class="section-title">Booking Confirmation</div>
      <p>Thank you ${details.renterName} for booking with Sikka!</p>
      <p>We have received your booking request successfully. Please proceed to the payment page to complete the payment process.</p>
    </div>

    <div class="section">
      <div class="section-title">Booking Details</div>
      <div class="detail-row">
        <span class="detail-label">Booking ID:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Car:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Pickup Date:</span>
        <span class="detail-value">${startDateStr}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Dropoff Date:</span>
        <span class="detail-value">${endDateStr}</span>
      </div>
      ${details.pickupTime ? `
      <div class="detail-row">
        <span class="detail-label">Pickup Time:</span>
        <span class="detail-value">${details.pickupTime}</span>
      </div>
      ` : ''}
      ${details.dropoffTime ? `
      <div class="detail-row">
        <span class="detail-label">Dropoff Time:</span>
        <span class="detail-value">${details.dropoffTime}</span>
      </div>
      ` : ''}
      <div class="detail-row">
        <span class="detail-label">Total Days:</span>
        <span class="detail-value">${details.totalDays}</span>
      </div>
      <div class="detail-row" style="border: none; padding-top: 15px; margin-top: 10px; border-top: 2px solid #FFB800;">
        <span class="detail-label" style="font-size: 18px;">Total Amount:</span>
        <span class="detail-value" style="font-size: 18px; color: #FFB800;">${amountStr} KWD</span>
      </div>
    </div>

    <div class="section">
      <p>If you have any questions, please contact us via email or phone.</p>
    </div>
  `

  try {
    await resend!.emails.send({
      from: FROM_EMAIL,
      to,
      subject: `تأكيد الحجز - Booking Confirmation #${details.bookingId}`,
      html: getEmailTemplate('Booking Confirmation', arabicContent, englishContent),
    })
  } catch (error) {
    console.error('Failed to send booking confirmation email:', error)
  }
}

export async function sendBookingNotificationToOwner(to: string, details: BookingDetails) {
  if (!isEmailEnabled()) return

  const startDateStr = details.startDate.toLocaleDateString('ar-SA')
  const endDateStr = details.endDate.toLocaleDateString('ar-SA')
  const amountStr = details.totalAmount.toFixed(2)

  const arabicContent = `
    <div class="section">
      <div class="section-title">حجز جديد لسيارتك</div>
      <p>مرحباً ${details.ownerName},</p>
      <p>تم الحصول على حجز جديد لسيارتك من قبل العميل ${details.renterName}.</p>
    </div>

    <div class="section">
      <div class="section-title">تفاصيل الحجز</div>
      <div class="detail-row">
        <span class="detail-label">رقم الحجز:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">اسم المستأجر:</span>
        <span class="detail-value">${details.renterName}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">السيارة:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">تاريخ الاستلام:</span>
        <span class="detail-value">${startDateStr}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">تاريخ التسليم:</span>
        <span class="detail-value">${endDateStr}</span>
      </div>
      ${details.pickupTime ? `
      <div class="detail-row">
        <span class="detail-label">وقت الاستلام:</span>
        <span class="detail-value">${details.pickupTime}</span>
      </div>
      ` : ''}
      ${details.dropoffTime ? `
      <div class="detail-row">
        <span class="detail-label">وقت التسليم:</span>
        <span class="detail-value">${details.dropoffTime}</span>
      </div>
      ` : ''}
      <div class="detail-row">
        <span class="detail-label">عدد الأيام:</span>
        <span class="detail-value">${details.totalDays}</span>
      </div>
      <div class="detail-row" style="border: none; padding-top: 15px; margin-top: 10px; border-top: 2px solid #FFB800;">
        <span class="detail-label" style="font-size: 18px;">المبلغ الإجمالي:</span>
        <span class="detail-value" style="font-size: 18px; color: #FFB800;">${amountStr} د.ك</span>
      </div>
    </div>

    <div class="section">
      <p>يرجى التحقق من بيانات الحجز والتأكد من توفر السيارة في الموعد المحدد.</p>
    </div>
  `

  const englishContent = `
    <div class="section">
      <div class="section-title">New Booking for Your Car</div>
      <p>Hello ${details.ownerName},</p>
      <p>You have received a new booking for your car from the customer ${details.renterName}.</p>
    </div>

    <div class="section">
      <div class="section-title">Booking Details</div>
      <div class="detail-row">
        <span class="detail-label">Booking ID:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Renter Name:</span>
        <span class="detail-value">${details.renterName}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Car:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Pickup Date:</span>
        <span class="detail-value">${startDateStr}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Dropoff Date:</span>
        <span class="detail-value">${endDateStr}</span>
      </div>
      ${details.pickupTime ? `
      <div class="detail-row">
        <span class="detail-label">Pickup Time:</span>
        <span class="detail-value">${details.pickupTime}</span>
      </div>
      ` : ''}
      ${details.dropoffTime ? `
      <div class="detail-row">
        <span class="detail-label">Dropoff Time:</span>
        <span class="detail-value">${details.dropoffTime}</span>
      </div>
      ` : ''}
      <div class="detail-row">
        <span class="detail-label">Total Days:</span>
        <span class="detail-value">${details.totalDays}</span>
      </div>
      <div class="detail-row" style="border: none; padding-top: 15px; margin-top: 10px; border-top: 2px solid #FFB800;">
        <span class="detail-label" style="font-size: 18px;">Total Amount:</span>
        <span class="detail-value" style="font-size: 18px; color: #FFB800;">${amountStr} KWD</span>
      </div>
    </div>

    <div class="section">
      <p>Please review the booking details and confirm that your car is available for the scheduled dates.</p>
    </div>
  `

  try {
    await resend!.emails.send({
      from: FROM_EMAIL,
      to,
      subject: `حجز جديد - New Booking #${details.bookingId}`,
      html: getEmailTemplate('New Booking', arabicContent, englishContent),
    })
  } catch (error) {
    console.error('Failed to send owner notification email:', error)
  }
}

export async function sendPaymentConfirmation(to: string, details: PaymentDetails) {
  if (!isEmailEnabled()) return

  const amountStr = details.totalAmount.toFixed(2)

  const arabicContent = `
    <div class="section">
      <div class="section-title">تأكيد الدفع</div>
      <p>شكراً ${details.renterName}!</p>
      <p>تم استلام دفعتك بنجاح ولقد تم تأكيد حجزك.</p>
    </div>

    <div class="section">
      <div class="section-title">تفاصيل الدفع</div>
      <div class="detail-row">
        <span class="detail-label">رقم الحجز:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">السيارة:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      ${details.paymentReference ? `
      <div class="detail-row">
        <span class="detail-label">رقم المرجع:</span>
        <span class="detail-value">${details.paymentReference}</span>
      </div>
      ` : ''}
      <div class="detail-row" style="border: none; padding-top: 15px; margin-top: 10px; border-top: 2px solid #FFB800;">
        <span class="detail-label" style="font-size: 18px;">المبلغ المدفوع:</span>
        <span class="detail-value" style="font-size: 18px; color: #FFB800;">${amountStr} د.ك</span>
      </div>
    </div>

    <div class="section">
      <p>حجزك الآن مؤكد وجاهز. يمكنك عرض تفاصيل الحجز الكاملة من خلال حسابك.</p>
      <p>شكراً لاختيارك سكا!</p>
    </div>
  `

  const englishContent = `
    <div class="section">
      <div class="section-title">Payment Confirmed</div>
      <p>Thank you ${details.renterName}!</p>
      <p>We have successfully received your payment and your booking is now confirmed.</p>
    </div>

    <div class="section">
      <div class="section-title">Payment Details</div>
      <div class="detail-row">
        <span class="detail-label">Booking ID:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Car:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      ${details.paymentReference ? `
      <div class="detail-row">
        <span class="detail-label">Reference Number:</span>
        <span class="detail-value">${details.paymentReference}</span>
      </div>
      ` : ''}
      <div class="detail-row" style="border: none; padding-top: 15px; margin-top: 10px; border-top: 2px solid #FFB800;">
        <span class="detail-label" style="font-size: 18px;">Amount Paid:</span>
        <span class="detail-value" style="font-size: 18px; color: #FFB800;">${amountStr} KWD</span>
      </div>
    </div>

    <div class="section">
      <p>Your booking is now confirmed and ready. You can view the complete booking details through your account.</p>
      <p>Thank you for choosing Sikka!</p>
    </div>
  `

  try {
    await resend!.emails.send({
      from: FROM_EMAIL,
      to,
      subject: `تأكيد الدفع - Payment Confirmation #${details.bookingId}`,
      html: getEmailTemplate('Payment Confirmed', arabicContent, englishContent),
    })
  } catch (error) {
    console.error('Failed to send payment confirmation email:', error)
  }
}

export async function sendBookingCancellation(to: string, details: BookingDetails) {
  if (!isEmailEnabled()) return

  const startDateStr = details.startDate.toLocaleDateString('ar-SA')
  const endDateStr = details.endDate.toLocaleDateString('ar-SA')

  const arabicContent = `
    <div class="section">
      <div class="section-title">إلغاء الحجز</div>
      <p>مرحباً ${details.renterName},</p>
      <p>تم إلغاء حجزك بنجاح. يمكنك إنشاء حجز جديد في أي وقت.</p>
    </div>

    <div class="section">
      <div class="section-title">تفاصيل الحجز الملغى</div>
      <div class="detail-row">
        <span class="detail-label">رقم الحجز:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">السيارة:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">تاريخ الاستلام:</span>
        <span class="detail-value">${startDateStr}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">تاريخ التسليم:</span>
        <span class="detail-value">${endDateStr}</span>
      </div>
    </div>

    <div class="section">
      <p>إذا كان لديك أي استفسارات أو تود إعادة حجز السيارة، يرجى الاتصال بنا.</p>
    </div>
  `

  const englishContent = `
    <div class="section">
      <div class="section-title">Booking Cancelled</div>
      <p>Hello ${details.renterName},</p>
      <p>Your booking has been successfully cancelled. You can create a new booking at any time.</p>
    </div>

    <div class="section">
      <div class="section-title">Cancelled Booking Details</div>
      <div class="detail-row">
        <span class="detail-label">Booking ID:</span>
        <span class="detail-value">${details.bookingId}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Car:</span>
        <span class="detail-value">${details.carTitle}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Pickup Date:</span>
        <span class="detail-value">${startDateStr}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Dropoff Date:</span>
        <span class="detail-value">${endDateStr}</span>
      </div>
    </div>

    <div class="section">
      <p>If you have any questions or would like to rebook the car, please contact us.</p>
    </div>
  `

  try {
    await resend!.emails.send({
      from: FROM_EMAIL,
      to,
      subject: `إلغاء الحجز - Booking Cancelled #${details.bookingId}`,
      html: getEmailTemplate('Booking Cancelled', arabicContent, englishContent),
    })
  } catch (error) {
    console.error('Failed to send cancellation email:', error)
  }
}
