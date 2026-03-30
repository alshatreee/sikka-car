import { z } from 'zod'

export const carListingSchema = z.object({
  title: z.string().min(2),
  year: z.coerce.number().min(2000).max(2100),
  dailyPrice: z.coerce.number().positive().max(500),
  area: z.string().min(2),
  city: z.string().optional(),
  origin: z.string().optional(),
  type: z.string().optional(),
  category: z.string().optional(),
  seats: z.coerce.number().optional(),
  transmission: z.enum(['AUTOMATIC', 'MANUAL', 'ELECTRIC']).optional(),
  smokingPolicy: z.string().optional(),
  distancePolicy: z.string().optional(),
  minAge: z.coerce.number().optional(),
  availabilityText: z.string().optional(),
  notes: z.string().optional(),
  images: z.array(z.string()).min(1),
  documentImages: z.array(z.string()).min(1),
})

export const bookingSchema = z.object({
  carId: z.string().min(1),
  startDate: z.string().min(1),
  endDate: z.string().min(1),
  pickupTime: z.string().optional(),
  dropoffTime: z.string().optional(),
  notes: z.string().max(500).optional(),
  civilId: z.string().regex(/^\d{12}$/).optional().or(z.literal('')),
  licenseNumber: z.string().optional(),
  civilIdImageFront: z.string().optional(),
  civilIdImageBack: z.string().optional(),
  licenseImageFront: z.string().optional(),
  licenseImageBack: z.string().optional(),
}).refine(
  (data) => {
    const start = new Date(data.startDate)
    const end = new Date(data.endDate)
    return end > start
  },
  { message: 'تاريخ النهاية يجب أن يكون بعد تاريخ البداية', path: ['endDate'] }
).refine(
  (data) => {
    const start = new Date(data.startDate)
    const end = new Date(data.endDate)
    const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
    return days <= 365
  },
  { message: 'مدة الحجز لا تتجاوز 365 يوم', path: ['endDate'] }
).refine(
  (data) => (data.civilId && data.civilId.length > 0) || (data.civilIdImageFront && data.civilIdImageFront.length > 0),
  { message: 'يرجى إدخال الرقم المدني أو رفع صورة البطاقة المدنية', path: ['civilId'] }
).refine(
  (data) => (data.licenseNumber && data.licenseNumber.length > 0) || (data.licenseImageFront && data.licenseImageFront.length > 0),
  { message: 'يرجى إدخال رقم الرخصة أو رفع صورة الرخصة', path: ['licenseNumber'] }
)
