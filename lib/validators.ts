import { z } from 'zod'

export const carListingSchema = z.object({
  title: z.string().min(2),
  year: z.coerce.number().min(2000).max(2100),
  dailyPrice: z.coerce.number().positive(),
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
  notes: z.string().optional(),
  civilId: z.string().optional(),
  licenseNumber: z.string().optional(),
  civilIdImage: z.string().optional(),
  licenseImage: z.string().optional(),
}).refine(
  (data) => (data.civilId && data.civilId.length > 0) || (data.civilIdImage && data.civilIdImage.length > 0),
  { message: 'يرجى إدخال الرقم المدني أو رفع صورة البطاقة المدنية', path: ['civilId'] }
).refine(
  (data) => (data.licenseNumber && data.licenseNumber.length > 0) || (data.licenseImage && data.licenseImage.length > 0),
  { message: 'يرجى إدخال رقم الرخصة أو رفع صورة الرخصة', path: ['licenseNumber'] }
)
